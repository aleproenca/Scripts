# Scripts

# Cisco FTDv Auto Scale no Azure (Customizado)

Este repositório contém scripts **customizados** para facilitar a implantação de um cluster **Cisco Threat Defense Virtual (FTDv)** com **Auto Scaling** no Microsoft Azure.

Baseado na documentação oficial da Cisco:  
**"Deploy a Threat Defense Virtual Cluster on Azure"** e no guia de Auto Scale para FTDv.

---

## 📋 Pré-requisitos

Antes de executar qualquer script, você **deve** criar manualmente os seguintes recursos:

- **Storage Account** (padrão ou Premium) na mesma região do deployment
- **File Share** dentro dessa Storage Account (usado pela Function App)

> **Importante**: A Storage Account e o File Share precisam ser criados **antes** de aplicar os templates ARM. Os scripts esperam que esses recursos já existam.

---

## 🛠 Arquivos do Repositório

### 1. `cria_vnets_e_subnets.json`

- Template ARM responsável por criar a **Virtual Network** e todas as **subnets** necessárias.
- Inclui:
  - Subnet de Management
  - Subnet Inside
  - Subnet Outside
  - Subnet CCL (Cluster Control Link)
  - Subnet para Function App (com delegation)

**Recomendação**: Execute este template primeiro.

### 2. `ftdcisco_custom.json` (ou `ftdcisco_custom.txt`)

- Template ARM customizado principal para o deployment completo do **FTDv Auto Scale**.
- Inclui:
  - Virtual Machine Scale Set (VMSS) com FTDv
  - External Load Balancer (ELB)
  - Internal Load Balancer (ILB)
  - Network Security Groups
  - Azure Function App + Logic App
  - Role Assignments necessárias
  - Integração com FMC (Firewall Management Center)

---

## 🚀 Ordem Recomendada de Deploy

1. Crie manualmente a **Storage Account** + **File Share**
2. Execute o template `cria_vnets_e_subnets.json`
3. Execute o template `ftdcisco_custom.json`

Você pode fazer o deploy via:
- Azure Portal (Deploy a custom template)
- Azure CLI
- Azure PowerShell
- GitHub Actions / Terraform + ARM, etc.

---

## ⚙️ Parâmetros Importantes

Os templates usam vários parâmetros customizáveis, entre eles:

- `resourceNamePrefix`
- `virtualNetworkName` / `virtualNetworkCidr`
- CIDRs das subnets (Management, Inside, Outside, CCL, Function App)
- `existingStorageAccountName` e `existingFileShareName`
- `ftdLicensingSku` (`byol` ou `payg`)
- `softwareVersion`
- `ftdvNodeCount`
- `autoscaling` (Enable/Disable)
- Credenciais do FMC, senhas, etc.

Ajuste os valores conforme sua necessidade antes do deploy.

---

## 📖 Documentação Oficial da Cisco

- [Deploy a Threat Defense Virtual Cluster on Azure](https://www.cisco.com/c/en/us/td/docs/security/secure-firewall/management-center/cluster/deploy-threat-defense-virtual-cluster-azure.html)
- [Deploy the Firewall Threat Defense Virtual Auto Scale Solution on Azure](https://www.cisco.com/c/en/us/td/docs/security/firepower/quick_start/consolidated_ftdv_gsg/threat-defense-virtual-77-gsg/m_deploy-the-firepower-threat-defense-virtual-for-azure-autoscale.html)

---

## ⚠️ Observações

- Este é um fork/customização dos templates oficiais da Cisco.
- Testado para facilitar o uso em ambientes reais (separação da criação da VNet +

