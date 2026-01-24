param swaName string
param backendResourceId string
param location string
param aadClientId string

@secure()
param aadClientSecret string

resource staticSite 'Microsoft.Web/staticSites@2022-09-01' existing = {
  name: swaName
}

resource swaAppSettings 'Microsoft.Web/staticSites/config@2022-09-01' = {
  parent: staticSite
  name: 'appsettings'
  properties: {
    AAD_CLIENT_ID: aadClientId
    AAD_CLIENT_SECRET: aadClientSecret
  }
}

resource linkedBackend 'Microsoft.Web/staticSites/linkedBackends@2022-09-01' = {
  parent: staticSite
  name: 'backend'
  properties: {
    backendResourceId: backendResourceId
    region: location
  }
}
