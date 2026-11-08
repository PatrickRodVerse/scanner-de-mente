# Scanner de Mente

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Pesquisador construindo seu laboratório local de interpretabilidade mecanística
no notebook Intel Core Ultra 5 125U, Windows x64 e 16 GB de RAM.

## Product Purpose

Executar e explorar activation patching em GPT-2, examinar features candidatas
de um SAE e navegar pelo grafo do código. O resultado deve distinguir observação,
efeito de intervenção e topologia permitida.

## Operating Context

O usuário confirmou a preferência por painel no navegador local. O backend Python
já existe. A interface chama processos locais, usa Graphify instalado separadamente
e exibe a memória disponível antes de permitir carregar o modelo.

## Capabilities and Constraints

CPU FP32; no máximo um trabalho por vez; captura de até 64 tokens; mínimo de
3 GiB disponíveis para o GPT-2. Servidor somente em loopback. Não carregar o modelo
ao abrir o painel. O primeiro experimento pré-treinado ainda não foi medido.

## Evidence on Hand

Código e testes de hooks, patching, SAE e Graphify; grafo real do repositório;
checkpoint GPT-2 local. A demonstração visual utiliza valores sintéticos, é
explicitamente identificada e não é salva como resultado experimental.

## Product Principles

- Mostrar unidades, controles e proveniência junto aos resultados.
- Reservar recursos do notebook para os experimentos.
- Conservar resultados anteriores quando um novo trabalho falha.
- Features e efeitos locais não recebem alegações de conceitos/circuitos completos.

## Open Decisions

Interface HTML/CSS/JavaScript e servidor Python da biblioteca padrão. Distribuição
Windows x64 por instalador Inno Setup, com runtime Python e dependências CPU
incluídos, atalhos e desinstalação. O painel permanece no navegador local.
