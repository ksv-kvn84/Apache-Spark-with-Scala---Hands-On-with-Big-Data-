# 1. Resource Group
terraform import azurerm_resource_group.rg "/subscriptions/<SUB_ID>/resourceGroups/<RG_NAME>"

# 2. Storage Account
terraform import module.storage_account.azurerm_storage_account.storage_account "/subscriptions/<SUB_ID>/resourceGroups/<RG_NAME>/providers/Microsoft.Storage/storageAccounts/<STORAGE_NAME>"

# 3. Storage Container
terraform import module.storage_account.azurerm_storage_container.storage_account_container[0] "/subscriptions/<SUB_ID>/resourceGroups/<RG_NAME>/providers/Microsoft.Storage/storageAccounts/<STORAGE_NAME>/blobServices/default/containers/<CONTAINER_NAME>"

# 4. Key Vault Access Policy
terraform import module.storage_account.azurerm_keyvault_access_policy.storage_keyvault_accesspolicy[0] "/subscriptions/<SUB_ID>/resourceGroups/<KV_RG>/providers/Microsoft.KeyVault/vaults/<KV_NAME>/objectId/<OBJECT_ID>"

# 5. Private Endpoint
terraform import 'module.storage_account.azurerm_private_endpoint.private_endpoint["blob"]' "/subscriptions/<SUB_ID>/resourceGroups/<RG_NAME>/providers/Microsoft.Network/privateEndpoints/<PE_NAME>"

# 6. UAMI
terraform import module.storage_account.azurerm_user_assigned_identity.storage_account_uami[0] "/subscriptions/<SUB_ID>/resourceGroups/<RG_NAME>/providers/Microsoft.ManagedIdentity/userAssignedIdentities/<UAMI_NAME>"

# 7. Null Resource (any string ID)
terraform import 'module.storage_account.null_resource.dns_update_checker["blob"]' "dns-checker-<STORAGE_NAME>-blob"
