import os
import sys
import argparse
import logging
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------

pools_to_setup = [
    {
        "instance_pool_name": "absss",
        "min_idle_instances": 0,
        "max_capacity": 250,
        "node_type_id": "Standard_DS3_v2",
        "idle_instance_autotermination_minutes": 15
    }
]

clusters_to_setup = [
    {
        "cluster_name": "exploration",
        "spark_version": "14.3.x-scala2.12",
        "node_type_id": "Standard_DS3_v2",
        "num_workers": 4
    }
]

# Permissions
default_permissions = {
    "access_control_list": [
        {"group_name": "admins", "permission_level": "CAN_MANAGE"}
    ]
}

default_interactive_permissions = {
    "access_control_list": [
        {"group_name": "users", "permission_level": "CAN_RESTART"}
    ]
}

special_interactive_permissions = {
    "access_control_list": [
        {"group_name": "power_users", "permission_level": "CAN_ATTACH_TO"}
    ]
}

# ------------------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# CLIENT
# ------------------------------------------------------------------------------

def get_client():
    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")
    if not host or not token:
        log.error("❌ Missing env vars: DATABRICKS_HOST or DATABRICKS_TOKEN")
        sys.exit(1)
    return WorkspaceClient(host=host, token=token)

# ------------------------------------------------------------------------------
# POOLS
# ------------------------------------------------------------------------------

def setup_pools(client):
    log.info("🚀 Setting up instance pools...")
    for pool_cfg in pools_to_setup:
        pool_name = pool_cfg["instance_pool_name"]
        existing = [p for p in client.instance_pools.list() if p.instance_pool_name == pool_name]
        if existing:
            log.info(f"Pool '{pool_name}' already exists — skipping.")
            continue

        log.info(f"Creating pool '{pool_name}'...")
        pool = client.instance_pools.create(**pool_cfg)

        # Set permissions immediately
        set_pool_permissions(client, pool.instance_pool_id, default_permissions)
    log.info("✅ Pool setup complete.")


def set_pool_permissions(client, pool_id, perms):
    """Sets permissions for a pool using REST API (SDK lacks direct method)."""
    import requests
    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")

    url = f"{host}/api/2.0/permissions/instance-pools/{pool_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = requests.patch(url, headers=headers, data=json.dumps(perms))
        if resp.status_code == 200:
            log.info(f"✅ Permissions applied to pool {pool_id}")
        else:
            log.warning(f"⚠️ Failed to set permissions for pool {pool_id}: {resp.text}")
    except Exception as e:
        log.error(f"❌ Error setting pool permissions: {e}")


def cleanup_old_pools(client, keep_prefixes=("generic",)):
    log.info("🧹 Cleaning up old pools...")
    for pool in client.instance_pools.list():
        name = pool.instance_pool_name.lower()
        if not any(name.startswith(prefix) for prefix in keep_prefixes):
            log.info(f"Deleting unused pool '{pool.instance_pool_name}'...")
            client.instance_pools.delete(pool.instance_pool_id)
    log.info("✅ Pool cleanup complete.")


def print_current_pools(client):
    log.info("📋 Current pools:")
    for pool in client.instance_pools.list():
        log.info(f" - {pool.instance_pool_name} (ID: {pool.instance_pool_id})")

# ------------------------------------------------------------------------------
# CLUSTERS
# ------------------------------------------------------------------------------

def setup_clusters(client):
    log.info("🚀 Setting up clusters...")
    for cfg in clusters_to_setup:
        name = cfg["cluster_name"]
        existing = [c for c in client.clusters.list() if c.cluster_name == name]
        if existing:
            log.info(f"Cluster '{name}' already exists — skipping.")
            continue

        log.info(f"Creating cluster '{name}'...")
        cluster = client.clusters.create(**cfg)
        # Example: set default interactive permissions
        set_cluster_permissions(client, cluster.cluster_id, default_interactive_permissions)
    log.info("✅ Cluster setup complete.")


def set_cluster_permissions(client, cluster_id, perms):
    import requests
    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")

    url = f"{host}/api/2.0/permissions/clusters/{cluster_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = requests.patch(url, headers=headers, data=json.dumps(perms))
        if resp.status_code == 200:
            log.info(f"✅ Permissions applied to cluster {cluster_id}")
        else:
            log.warning(f"⚠️ Failed to set cluster permissions for {cluster_id}: {resp.text}")
    except Exception as e:
        log.error(f"❌ Error setting cluster permissions: {e}")

# ------------------------------------------------------------------------------
# CLUSTER CLEANUP (Optimized)
# ------------------------------------------------------------------------------

def iter_clusters_to_delete(client, retained_clusters=None):
    """Stream through clusters lazily, skipping job clusters and exclusions."""
    retained_lower = {r.lower() for r in (retained_clusters or [])}

    for c in client.clusters.list():  # generator, paged
        name = c.cluster_name.lower()
        if c.cluster_source == "JOB":
            continue
        if name in retained_lower:
            continue
        if name.startswith("generic"):
            continue
        if name.endswith("pic") or name.endswith("explorer"):
            continue
        yield c


def cleanup_clusters(client, retained_clusters=None, max_workers=10):
    """Concurrent, efficient deletion of unwanted clusters."""
    to_delete = list(iter_clusters_to_delete(client, retained_clusters))
    log.info(f"🧹 Preparing to delete {len(to_delete)} clusters...")

    def delete_cluster(c):
        try:
            client.clusters.permanent_delete(c.cluster_id)
            log.info(f"✅ Deleted '{c.cluster_name}'")
            return True
        except Exception as e:
            log.error(f"❌ Failed to delete '{c.cluster_name}': {e}")
            return False

    deleted = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(delete_cluster, c) for c in to_delete]
        for f in as_completed(futures):
            if f.result():
                deleted += 1

    log.info(f"✅ Cleanup complete — deleted {deleted}/{len(to_delete)} clusters.")

# ------------------------------------------------------------------------------
# MAIN DISPATCH
# ------------------------------------------------------------------------------

def main(task: str):
    client = get_client()
    task = task.lower()

    if task == "pools":
        setup_pools(client)
    elif task == "cleanup_pools":
        cleanup_old_pools(client)
    elif task == "list_pools":
        print_current_pools(client)
    elif task == "clusters":
        setup_clusters(client)
    elif task == "cleanup_clusters":
        cleanup_clusters(client, retained_clusters=["exploration", "shared"])
    elif task == "permissions":
        log.info("Permissions task placeholder — permissions are applied per resource.")
    else:
        log.error(f"❌ Unknown task: {task}")
        sys.exit(1)

    log.info(f"✅ Task '{task}' completed successfully.")

# ------------------------------------------------------------------------------
# ENTRY POINT (ADO)
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Databricks Workspace Automation")
    parser.add_argument("--task", required=True,
                        help="Task to run: pools | cleanup_pools | clusters | cleanup_clusters | list_pools | permissions")
    args = parser.parse_args()
    main(args.task)
