#!/bin/bash

# This script automates the deployment process to Azure for the Team C application.

# Exit immediately if a command exits with a non-zero status
set -e

# Variables
RESOURCE_GROUP="your-resource-group" # Update with your resource group name
APP_SERVICE_NAME="shopsmart-backend-staging" # Update with your App Service name
AZURE_SUBSCRIPTION="your-azure-subscription" # Update with your Azure subscription ID
BICEP_FILE="../azure/webapp.bicep" # Path to the Bicep file
SERVICE_PLAN_FILE="../azure/service-plan.json" # Path to the service plan file
APPINSIGHTS_CONNECTION_STRING="${APPLICATIONINSIGHTS_CONNECTION_STRING:-}" # Exported connection string

# Login to Azure
echo "Logging in to Azure..."
az login --service-principal -u $AZURE_CLIENT_ID -p $AZURE_CLIENT_SECRET --tenant $AZURE_TENANT_ID

# Set the subscription
echo "Setting Azure subscription..."
az account set --subscription $AZURE_SUBSCRIPTION

# Deploy the Bicep template
echo "Deploying Azure resources using Bicep..."
az deployment group create --resource-group $RESOURCE_GROUP --template-file $BICEP_FILE --parameters appServiceName=$APP_SERVICE_NAME appInsightsConnectionString="$APPINSIGHTS_CONNECTION_STRING"

# Deploy the App Service Plan
echo "Deploying App Service Plan..."
az deployment group create --resource-group $RESOURCE_GROUP --template-file $SERVICE_PLAN_FILE

# Configure Application Insights
echo "Configuring Application Insights..."
az monitor app-insights component create --app $APP_SERVICE_NAME --location "East US" --resource-group $RESOURCE_GROUP --application-type web

# Set environment variables for the App Service
echo "Setting environment variables..."
if [ -n "$APPINSIGHTS_CONNECTION_STRING" ]; then
  az webapp config appsettings set --name $APP_SERVICE_NAME --resource-group $RESOURCE_GROUP --settings "APPLICATIONINSIGHTS_CONNECTION_STRING=$APPINSIGHTS_CONNECTION_STRING"
else
  echo "APPLICATIONINSIGHTS_CONNECTION_STRING not set; skipping app settings update"
fi

# Deploy the application
echo "Deploying the application to Azure App Service..."
az webapp up --name $APP_SERVICE_NAME --resource-group $RESOURCE_GROUP --runtime "PYTHON|3.11" --sku F1

echo "Deployment completed successfully!"
