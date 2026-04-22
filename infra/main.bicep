@description('リソースのプレフィックス')
param prefix string = 'azlearn'

@description('デプロイリージョン')
param location string = resourceGroup().location

@description('Azure OpenAI デプロイメント名')
param openAiDeployment string = 'gpt-4o'

// --- Cosmos DB ---
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: '${prefix}-cosmos'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [{ locationName: location, failoverPriority: 0 }]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    // キーベース認証を無効化 → Managed Identity のみ許可
    disableLocalAuth: true
  }
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: 'ms-learning'
  properties: { resource: { id: 'ms-learning' } }
}

var containers = [
  { name: 'learning_paths', partitionKey: '/id' }
  { name: 'units',          partitionKey: '/module_id' }
  { name: 'quizzes',        partitionKey: '/unit_id' }
  { name: 'user_progress',  partitionKey: '/user_id' }
]

resource cosmosContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [for c in containers: {
  parent: cosmosDb
  name: c.name
  properties: {
    resource: {
      id: c.name
      partitionKey: { paths: [c.partitionKey], kind: 'Hash' }
    }
  }
}]

// --- Storage (Functions 用) ---
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: '${prefix}st'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
}

// --- App Service Plan (Consumption) ---
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${prefix}-plan'
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' }
  kind: 'functionapp'
  properties: { reserved: true }
}

// --- Azure Functions ---
resource funcApp 'Microsoft.Web/sites@2023-12-01' = {
  name: '${prefix}-func'
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }  // Managed Identity 有効化
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      pythonVersion: '3.11'
      appSettings: [
        { name: 'AzureWebJobsStorage',        value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value}' }
        { name: 'FUNCTIONS_WORKER_RUNTIME',   value: 'python' }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'COSMOS_DB_ENDPOINT',         value: cosmosAccount.properties.documentEndpoint }
        { name: 'COSMOS_DB_DATABASE',         value: 'ms-learning' }
        { name: 'AZURE_OPENAI_ENDPOINT',      value: '' }  // デプロイ後に設定
        { name: 'AZURE_OPENAI_DEPLOYMENT',    value: openAiDeployment }
      ]
    }
    httpsOnly: true
  }
}

// --- Cosmos DB へのデータ寄稿者ロール付与 (Managed Identity) ---
var cosmosRoleId = '00000000-0000-0000-0000-000000000002'  // Cosmos DB Built-in Data Contributor
resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, funcApp.id, cosmosRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosRoleId}'
    principalId: funcApp.identity.principalId
    scope: cosmosAccount.id
  }
}

// --- Static Web Apps ---
resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${prefix}-swa'
  location: location
  sku: { name: 'Free', tier: 'Free' }
  properties: {}
}

output functionAppName string = funcApp.name
output staticWebAppName string = swa.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
