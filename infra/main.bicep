// =====================================================================
// Microsoft Learn 学習サポート — 本番リソース定義
// =====================================================================
// 構成:
//   Static Web Apps (Standard)  ──linkedBackend──▶  Functions (Linux Consumption)
//                  │                                       │
//                  └─ Entra ID 認証 (admin ロール)         ├─ Cosmos DB (MI / disableLocalAuth)
//                                                          ├─ Foundry Agents (Bearer token / MI)
//                                                          └─ Storage (Functions ホスト用)
// =====================================================================

@description('リソースのプレフィックス（小文字英数字 4-12 文字）')
@minLength(4)
@maxLength(12)
param prefix string = 'mslearn'

@description('デプロイリージョン (SWA 以外のリソース用)')
param location string = resourceGroup().location

@description('Static Web Apps のリージョン (Standard SKU 対応: westus2, centralus, eastus2, westeurope, eastasia)')
@allowed([
  'westus2'
  'centralus'
  'eastus2'
  'westeurope'
  'eastasia'
])
param swaLocation string = 'eastasia'

// ---- 既存リソース参照 ---- //
@description('既存 Cosmos DB アカウント名')
param existingCosmosAccountName string = 'cosmos-training-murokawa'

@description('既存 Cosmos DB データベース名（backend が参照する論理DB）')
param existingCosmosDatabaseName string = 'cosmos-training-murokawa'

// ---- Foundry / Azure OpenAI （既存リソース、URL のみ参照） ---- //
@description('既存 Azure OpenAI / Foundry プロジェクトのエンドポイント (例: https://foundry-xxx.services.ai.azure.com/api/projects/proj-default)')
param openAiEndpoint string

@description('Azure OpenAI デプロイメント名')
param openAiDeployment string = 'gpt-4o'

@description('Foundry summary-agent のフルURL (api-version含む)')
param foundryAgentUrlSummary string

@description('Foundry quiz-agent のフルURL (api-version含む)')
param foundryAgentUrlQuiz string

// ---- 認証 ---- //
@description('Entra ID アプリ登録 — クライアント ID (SWA 認証用)')
param aadClientId string

@description('Entra ID アプリ登録 — クライアント シークレット (SWA 認証用)')
@secure()
param aadClientSecret string

// ---- SWA リポジトリ連携 (任意) ---- //
@description('GitHub リポジトリ URL (Static Web Apps の repositoryUrl 用、未指定なら手動デプロイ)')
param swaRepositoryUrl string = ''

@description('GitHub ブランチ名')
param swaBranch string = 'main'

// --------------------------------------------------------------------- //
// 既存 Cosmos DB を参照（コンテナ・DB は既存のものを利用）
// --------------------------------------------------------------------- //
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: existingCosmosAccountName
}

// --------------------------------------------------------------------- //
// Storage (Functions ランタイム用)
// --------------------------------------------------------------------- //
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: '${prefix}st'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { allowBlobPublicAccess: false }
}

// --------------------------------------------------------------------- //
// Application Insights (任意。Functions の監視用)
// --------------------------------------------------------------------- //
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${prefix}-ai'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// --------------------------------------------------------------------- //
// App Service Plan (Functions Consumption / Linux)
// --------------------------------------------------------------------- //
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${prefix}-plan'
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' }
  kind: 'functionapp'
  properties: { reserved: true }
}

// --------------------------------------------------------------------- //
// Azure Functions (Python 3.11, Linux)
// --------------------------------------------------------------------- //
resource funcApp 'Microsoft.Web/sites@2023-12-01' = {
  name: '${prefix}-func'
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      ftpsState: 'Disabled'
      appSettings: [
        { name: 'AzureWebJobsStorage', value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'COSMOS_DB_ENDPOINT', value: cosmosAccount.properties.documentEndpoint }
        { name: 'COSMOS_DB_DATABASE', value: existingCosmosDatabaseName }
        { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
        { name: 'AZURE_OPENAI_DEPLOYMENT', value: openAiDeployment }
        { name: 'FOUNDRY_AGENT_URL_SUMMARY', value: foundryAgentUrlSummary }
        { name: 'FOUNDRY_AGENT_URL_QUIZ', value: foundryAgentUrlQuiz }
        // 本番ではスクレイピングを完全に無効化（管理者がローカル実行する想定）
        { name: 'DISABLE_SCRAPE', value: 'true' }
        // 本番では絶対に LOCAL_ADMIN_BYPASS を有効化しないこと（明示的に false）
        { name: 'LOCAL_ADMIN_BYPASS', value: 'false' }
      ]
      cors: {
        // SWA からのリクエストは linkedBackend 経由 (同一オリジン) なので CORS は基本不要
        // 緊急の動作確認用に SWA hostname を許可
        allowedOrigins: [
          'https://${swa.properties.defaultHostname}'
        ]
      }
    }
  }
}

// --------------------------------------------------------------------- //
// Cosmos DB データ寄稿者ロール → Functions の Managed Identity
// --------------------------------------------------------------------- //
var cosmosBuiltInDataContributor = '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'

resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, funcApp.id, 'cosmos-contrib')
  properties: {
    roleDefinitionId: cosmosBuiltInDataContributor
    principalId: funcApp.identity.principalId
    scope: cosmosAccount.id
  }
}

// --------------------------------------------------------------------- //
// Static Web Apps (Standard tier — linkedBackend に必須)
// --------------------------------------------------------------------- //
resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${prefix}-swa'
  location: swaLocation
  sku: { name: 'Standard', tier: 'Standard' }
  properties: {
    repositoryUrl: empty(swaRepositoryUrl) ? null : swaRepositoryUrl
    branch: empty(swaRepositoryUrl) ? null : swaBranch
    buildProperties: {
      appLocation: 'frontend'
      outputLocation: 'dist'
      appBuildCommand: 'npm run build'
      // API は linkedBackend で別 Function App を使うので skipApiBuild
      skipGithubActionWorkflowGeneration: true
    }
  }
}

// SWA の App Settings (staticwebapp.config.json から ${AAD_CLIENT_ID} 等を参照)
resource swaAppSettings 'Microsoft.Web/staticSites/config@2023-12-01' = {
  parent: swa
  name: 'appsettings'
  properties: {
    AAD_CLIENT_ID: aadClientId
    AAD_CLIENT_SECRET: aadClientSecret
  }
}

// SWA から Function App を /api/* として公開
resource swaLinkedBackend 'Microsoft.Web/staticSites/linkedBackends@2023-12-01' = {
  parent: swa
  name: 'backend1'
  properties: {
    backendResourceId: funcApp.id
    region: location
  }
}

// --------------------------------------------------------------------- //
// Outputs
// --------------------------------------------------------------------- //
output functionAppName string = funcApp.name
output functionAppHostname string = funcApp.properties.defaultHostName
output staticWebAppName string = swa.name
output staticWebAppHostname string = swa.properties.defaultHostname
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosAccountName string = cosmosAccount.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
