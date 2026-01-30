targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

// Optional parameters to override the default azd resource naming conventions. Update the main.parameters.json file to provide values.
param applicationInsightsDashboardName string = ''
param applicationInsightsName string = ''
param cosmosAccountName string = ''
param keyVaultName string = ''
param logAnalyticsName string = ''
param resourceGroupName string = ''
param webServiceName string = ''
param containerRegistryName string = ''
param containerAppsEnvironmentName string = ''
param containerAppName string = ''

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Azure AD Application (client) ID for authentication')
param aadClientId string = ''

@secure()
@description('Azure AD Application client secret for authentication')
param aadClientSecret string = ''

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// Organize resources in a resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: !empty(resourceGroupName) ? resourceGroupName : '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

// The application frontend (Standard tier for custom auth)
module web 'br/public:avm/res/web/static-site:0.3.0' = {
  name: 'staticweb'
  scope: rg
  params: {
    name: !empty(webServiceName) ? webServiceName : '${abbrs.webStaticSites}web-${resourceToken}'
    location: location
    provider: 'Custom'
    sku: 'Standard'
    tags: union(tags, { 'azd-service-name': 'web' })
  }
}

// Configure SWA: linked backend + Azure AD app settings
module swaConfig './app/swa-config.bicep' = {
  name: 'swa-config'
  scope: rg
  params: {
    swaName: web.outputs.name
    backendResourceId: containerApp.outputs.resourceId
    location: location
    aadClientId: aadClientId
    aadClientSecret: aadClientSecret
  }
}

// Container Registry for storing Docker images
module containerRegistry 'br/public:avm/res/container-registry/registry:0.3.1' = {
  name: 'containerregistry'
  scope: rg
  params: {
    name: !empty(containerRegistryName) ? containerRegistryName : '${abbrs.containerRegistryRegistries}${resourceToken}'
    location: location
    tags: tags
    acrSku: 'Basic'
    acrAdminUserEnabled: true
  }
}

// Container Apps Environment
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.5.2' = {
  name: 'containerappsenvironment'
  scope: rg
  params: {
    name: !empty(containerAppsEnvironmentName) ? containerAppsEnvironmentName : '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    tags: tags
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
  }
}

// Container App for the API
module containerApp 'br/public:avm/res/app/container-app:0.4.1' = {
  name: 'containerapp'
  scope: rg
  params: {
    name: !empty(containerAppName) ? containerAppName : '${abbrs.appContainerApps}api-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'api' })
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    managedIdentities: {
      systemAssigned: true
    }
    containers: [
      {
        name: 'api'
        image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        resources: {
          cpu: '0.5'
          memory: '1Gi'
        }
        env: [
          { name: 'AZURE_COSMOS_CONNECTION_STRING_KEY', value: cosmos.outputs.connectionStringKey }
          { name: 'AZURE_COSMOS_DATABASE_NAME', value: cosmos.outputs.databaseName }
          { name: 'AZURE_KEY_VAULT_ENDPOINT', value: keyVault.outputs.uri }
          { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: monitoring.outputs.applicationInsightsConnectionString }
        ]
      }
    ]
    registries: [
      {
        server: containerRegistry.outputs.loginServer
        username: containerRegistry.outputs.name
        passwordSecretRef: 'acr-password'
      }
    ]
    secrets: {
      secureList: [
        {
          name: 'acr-password'
          value: containerRegistry.outputs.name
        }
      ]
    }
    ingressTargetPort: 3100
    ingressExternal: true
    scaleMinReplicas: 0
    scaleMaxReplicas: 1
  }
}

// Give the API access to KeyVault
module accessKeyVault 'br/public:avm/res/key-vault/vault:0.5.1' = {
  name: 'accesskeyvault'
  scope: rg
  params: {
    name: keyVault.outputs.name
    enableRbacAuthorization: false
    enableVaultForDeployment: false
    enableVaultForTemplateDeployment: false
    enablePurgeProtection: false
    sku: 'standard'
    accessPolicies: [
      {
        objectId: containerApp.outputs.systemAssignedMIPrincipalId
        permissions: {
          secrets: [ 'get', 'list' ]
        }
      }
      {
        objectId: principalId
        permissions: {
          secrets: [ 'get', 'list' ]
        }
      }
    ]
  }
}

// The application database
module cosmos './app/db-avm.bicep' = {
  name: 'cosmos'
  scope: rg
  params: {
    accountName: !empty(cosmosAccountName) ? cosmosAccountName : '${abbrs.documentDBDatabaseAccounts}${resourceToken}'
    location: location
    tags: tags
    keyVaultResourceId: keyVault.outputs.resourceId
  }
}

// Create a keyvault to store secrets
module keyVault 'br/public:avm/res/key-vault/vault:0.5.1' = {
  name: 'keyvault'
  scope: rg
  params: {
    name: !empty(keyVaultName) ? keyVaultName : '${abbrs.keyVaultVaults}${resourceToken}'
    location: location
    tags: tags
    enableRbacAuthorization: false
    enableVaultForDeployment: false
    enableVaultForTemplateDeployment: false
    enablePurgeProtection: false
    sku: 'standard'
  }
}

// Monitor application with Azure Monitor
module monitoring 'br/public:avm/ptn/azd/monitoring:0.1.0' = {
  name: 'monitoring'
  scope: rg
  params: {
    applicationInsightsName: !empty(applicationInsightsName) ? applicationInsightsName : '${abbrs.insightsComponents}${resourceToken}'
    logAnalyticsName: !empty(logAnalyticsName) ? logAnalyticsName : '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsDashboardName: !empty(applicationInsightsDashboardName) ? applicationInsightsDashboardName : '${abbrs.portalDashboards}${resourceToken}'
    location: location
    tags: tags
  }
}

// Data outputs
output AZURE_COSMOS_CONNECTION_STRING_KEY string = cosmos.outputs.connectionStringKey
output AZURE_COSMOS_DATABASE_NAME string = cosmos.outputs.databaseName

// App outputs
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
output AZURE_KEY_VAULT_ENDPOINT string = keyVault.outputs.uri
output AZURE_KEY_VAULT_NAME string = keyVault.outputs.name
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output SERVICE_API_URI string = 'https://${containerApp.outputs.fqdn}'
output REACT_APP_WEB_BASE_URL string = 'https://${web.outputs.defaultHostname}'
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
