#!/bin/bash
set -euo pipefail

echo "=== Terraform Dynamic Import Script (Azure DevOps) ==="

TFVARS_FILE="$1"

if [[ -z "${TFVARS_FILE:-}" ]]; then
  echo "ERROR: No tfvars file supplied."
  exit 1
fi

if [[ ! -f "$TFVARS_FILE" ]]; then
  echo "ERROR: File '$TFVARS_FILE' not found."
  exit 1
fi

echo "Using tfvars: $TFVARS_FILE"

# -------- helper: robust tfvars parser ---------------------
get_var() {
  local var_name="$1"
  local value
  value=$(grep -E "^\s*$var_name\s*=" "$TFVARS_FILE" \
    | head -1 \
    | sed -E 's/.*=\s*//; s/#.*//; s/^"//; s/"$//' \
    | tr -d '[:space:]')

  if [[ -z "$value" ]]; then
    echo "ERROR: Variable '$var_name' not found in $TFVARS_FILE" >&2
    exit 1
  fi

  echo "$value"
}

# -------- load variables -----------------------------------
SUBSCRIPTION_ID=$(get_var subscription_id)
RESOURCE_GROUP_NAME=$(get_var resource_group_name)
STORAGE_ACCOUNT_NAME=$(get_var storage_account_name)
CONTAINER_NAME_0=$(get_var container_name_0)
KEYVAULT_RG_NAME=$(get_var keyvault_rg_name)
KEYVAULT_NAME=$(get_var keyvault_name)
OBJECT_ID_0=$(get_var keyvault_policy_object_id_0)
PE_BLOB_NAME=$(get_var private_endpoint_blob_name)
UAMI_NAME_0=$(get_var uami_name_0)

echo "Loaded values:"
echo "  SUBSCRIPTION_ID     = $SUBSCRIPTION_ID"
echo "  RESOURCE_GROUP_NAME = $RESOURCE_GROUP_NAME"
echo "  STORAGE_ACCOUNT_NAME= $STORAGE_ACCOUNT_NAME"
echo "  CONTAINER_NAME_0    = $CONTAINER_NAME_0"
echo "  KEYVAULT_RG_NAME    = $KEYVAULT_RG_NAME"
echo "  KEYVAULT_NAME       = $KEYVAULT_NAME"
echo "  OBJECT_ID_0         = $OBJECT_ID_0"
echo "  PE_BLOB_NAME        = $PE_BLOB_NAME"
echo "  UAMI_NAME_0         = $UAMI_NAME_0"

echo "=== Running terraform imports ==="

terraform init -input=false >/dev/null

terraform import \
  azurerm_resource_group.rg \
  "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME"

terraform import \
  module.storage_account.azurerm_storage_account.storage_account \
  "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME"

terraform import \
  module.storage_account.azurerm_storage_container.storage_account_container[0] \
  "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME/blobServices/default/containers/$CONTAINER_NAME_0"

terraform import \
  module.storage_account.azurerm_keyvault_access_policy.storage_keyvault_accesspolicy[0] \
  "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$KEYVAULT_RG_NAME/providers/Microsoft.KeyVault/vaults/$KEYVAULT_NAME/objectId/$OBJECT_ID_0"

terraform import \
  'module.storage_account.azurerm_private_endpoint.private_endpoint["blob"]' \
  "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Network/privateEndpoints/$PE_BLOB_NAME"

terraform import \
  module.storage_account.azurerm_user_assigned_identity.storage_account_uami[0] \
  "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.ManagedIdentity/userAssignedIdentities/$UAMI_NAME_0"

terraform import \
  'module.storage_account.null_resource.dns_update_checker["blob"]' \
  "dns-checker-$STORAGE_ACCOUNT_NAME-blob"

echo "=== Import complete ==="
