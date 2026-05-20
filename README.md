# Cisco FTDv Auto Scale no Azure (Customizado)

Este repositório contém templates ARM customizados para facilitar a implantação de um cluster **Cisco Threat Defense Virtual (FTDv)** com **Auto Scaling** no Microsoft Azure.

## 🛠 Arquivos do repositório

- `cria_ambiente_base.json`  
  Cria os objetos base necessários para o ambiente:
  - Storage Account
  - Azure File Share
  - Virtual Network
  - Subnets: Management, Inside, Outside, CCL e Function App (com delegation para `Microsoft.Web/serverfarms`)

- `cria_ambiente_base.parameters.example.json`  
  Exemplo de parâmetros para o template `cria_ambiente_base.json`.

- `cria_storage`  
  Template separado para criar apenas Storage Account + File Share.

- `cria_vnets_e_subnets`  
  Template separado para criar apenas VNet + subnets.

- `ftdcisco_custom.txt`  
  Template ARM principal do deployment FTDv Auto Scale (VMSS, LBs, Function App, Logic App, integrações e role assignments).

## 🚀 Ordem recomendada de deploy

1. Execute `cria_ambiente_base.json` para preparar os pré-requisitos de rede e storage.
2. Execute o template principal `ftdcisco_custom.txt`.

## Azure CLI (exemplo)

```bash
az deployment group create \
  --resource-group <seu-resource-group> \
  --template-file cria_ambiente_base.json \
  --parameters @cria_ambiente_base.parameters.example.json
```

Depois, aplique o template principal:

```bash
az deployment group create \
  --resource-group <seu-resource-group> \
  --template-file ftdcisco_custom.txt \
  --parameters <seus-parametros-do-ftd>
```

## ⚙️ Parâmetros importantes no template principal

- `existingStorageAccountName`
- `existingFileShareName`
- `virtualNetworkName`
- `mgmtSubnet`, `insideSubnet`, `outsideSubnet`, `cclSubnet`, `functionAppSubnet`

Garanta que os valores acima coincidam com os recursos criados no template de ambiente base.

## 📖 Documentação oficial da Cisco

- [Deploy a Threat Defense Virtual Cluster on Azure](https://www.cisco.com/c/en/us/td/docs/security/secure-firewall/management-center/cluster/deploy-threat-defense-virtual-cluster-azure.html)
- [Deploy the Firewall Threat Defense Virtual Auto Scale Solution on Azure](https://www.cisco.com/c/en/us/td/docs/security/firepower/quick_start/consolidated_ftdv_gsg/threat-defense-virtual-77-gsg/m_deploy-the-firepower-threat-defense-virtual-for-azure-autoscale.html)
