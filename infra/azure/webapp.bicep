param appName string
param appServicePlanName string
param location string = resourceGroup().location
param sku string = 'S1'
@secure()
param appInsightsConnectionString string = ''

resource appServicePlan 'Microsoft.Web/serverfarms@2021-02-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: sku
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    name: appServicePlanName
    workerSize: '0'
    numberOfWorkers: 1
    isSpot: false
  }
}

resource webApp 'Microsoft.Web/sites@2021-02-01' = {
  name: appName
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      appSettings: [
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
      ]
    }
  }
}

output webAppUrl string = webApp.defaultHostName
