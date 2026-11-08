# Scanner de Mente — notas anteriores do laboratório

Estas notas preservam o histórico técnico em português. Para a instalação e a
interface atuais, consulte o [guia em inglês](../INSTALL.md).

O Scanner de Mente ensina interpretabilidade por meio de intervenções medidas em
modelos de linguagem. O primeiro caso acompanha a preferência entre dois nomes no
GPT‑2 Small. A interface pública compara o contexto com troca, a restauração do nome
e duas fixações em posições diferentes. Cada escolha reapresenta uma medição em CPU.

## Estudo interativo para GitHub Pages

`site/` é a página pública estática. Para ver localmente, execute na raiz do projeto:

```powershell
python -m http.server 8766 --bind 127.0.0.1 --directory site
```

Abra <http://127.0.0.1:8766/>. O navegador lê `site/ioi.json`. As 24 intervenções da
varredura e os quatro casos foram reproduzidos com o checkpoint fixado. Para gerar
novamente o JSON no ambiente Python do laboratório, execute:

```powershell
python -m lab.ioi_case --output site/ioi.json
node tests/test_public_case.mjs
```

Depois de enviar o código a um repositório, escolha **Settings → Pages → GitHub Actions**
e execute **Publicar Scanner de Mente** na aba **Actions**. O workflow manual envia
somente `site/` ao Pages. O endereço aparece no ambiente `github-pages` após a execução.
[Documentação do GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

## Laboratório local de interpretabilidade

Primeira versão prática para Windows x64, Intel Core Ultra 5 125U e 16 GB de RAM.
Executa intervenções em GPT-2 Small, coleta ativações de uma camada, treina um SAE
educacional e usa o **Graphify real** para visualizar o código e as intervenções.

O alvo inicial é uma computação delimitada: **identificar para quem um objeto foi
entregue**. Isso permite medir uma mudança causal na preferência entre dois nomes.
Não é uma leitura de pensamentos nem uma explicação completa do raciocínio.

## Interface visual local

Abra `scripts/abrir-painel.cmd` com dois cliques. Ele inicia o servidor e abre o
painel no navegador em **http://127.0.0.1:8765**. Mantenha o terminal aberto enquanto
usa o laboratório; `Ctrl+C` encerra o servidor.
Se o painel já estiver em execução, o atalho reutiliza o servidor existente.

Também é possível iniciar pelo PowerShell na raiz do projeto:

```powershell
.venv/Scripts/python.exe -X utf8 -m lab.ui --open --graphify-python C:/Python314/python.exe
```

O painel permite editar os dois prompts e os nomes, escolher varredura curta ou
completa, executar activation patching, acompanhar RAM/logs, selecionar células do
mapa camada × token com mouse ou setas, alternar recuperação/efeito em logits e
exportar o resultado real em JSON. O servidor não carrega o GPT-2 na inicialização;
usa um processo separado por trabalho e não aceita execuções simultâneas.

**Explorar demonstração** ativa valores sintéticos claramente identificados, sem
executar modelo nem salvar resultado. O estado inicial não contém medições
inventadas. A vista **Features do SAE** lê métricas e prefixos já treinados em
`artifacts/sae/`; coleta/treino continuam nos comandos abaixo. A vista do repositório
abre o Graphify e permite atualizar o mapa. Resultados gerados pelo terminal também
aparecem no painel; o grafo experimental precisa ser gerado depois do resultado.

A interface, inclusive fontes, funciona sem CDN. Os grafos HTML padrão do Graphify
continuam usando vis-network da CDN, em iframes isolados. O servidor escuta somente
em loopback, verifica Host/Origin, limita corpos JSON e serve apenas os arquivos do
painel e os dois grafos permitidos. Não é um servidor para exposição na rede.

Testes adicionais da interface:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_ui.py -v
node tests/test_ui_data.mjs
```

## 1. Hardware e ambiente

- Python **3.11**, venv local `.venv`; PyTorch **2.10.0 CPU**, Transformers
  **4.57.6**, psutil **7.2.2**. Versões fixadas como base reproduzível, sem alegar
  serem as versões mais recentes.
- CPU FP32, modo eager, batch 1, até 64 tokens, `eval()`, `inference_mode()`,
  `use_cache=False`. Hooks temporários removidos inclusive em caso de exceção.
- Quatro threads como ponto inicial. Comparar `--threads 2`, `4`, `8` em runs
  separados antes de escolher por desempenho; isso não fixa afinidade nos P-cores.
- Checagem de **3 GiB de RAM disponíveis antes de carregar o modelo**. Treino SAE
  exige ao menos 1 GiB disponível e verifica uma estimativa das dimensões pedidas.
  Isso é uma margem preventiva, não uma garantia contra pressão de outros apps.
- Os 9 GB anunciados como memória compartilhada da iGPU disputam os mesmos 16 GB
  físicos. Não são RAM adicional. Não usar contextos grandes nem batch paralelo.
- Reservar inicialmente cerca de **3–5 GB de disco**, como estimativa incluindo
  venv, cache de instalação e checkpoint. Somente um formato de pesos é baixado:
  `model.safetensors`, com revisão do modelo fixada no código.

O IPEX encerrou o desenvolvimento após 2.8 e não é uma base adequada para um novo
projeto. [Aviso oficial](https://intel.github.io/intel-extension-for-pytorch/latest/).
O suporte XPU documentado cita Meteor Lake-H/Arc, sem confirmar esta combinação
125U/Intel Graphics 4 Xe; não foi validado neste equipamento.
[Tabela PyTorch](https://docs.pytorch.org/docs/main/notes/get_start_xpu.html).

OpenVINO pode aproveitar CPU/iGPU/NPU para inferência compilada, inclusive saídas
intermediárias explicitamente expostas. Intervenções Python em blocos eager não
migram automaticamente para esse backend; seria outra etapa de implementação e
validação. [NPU OpenVINO](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/npu-device.html).
DirectML também fica para um experimento separado de compatibilidade.
[Documentação Microsoft](https://learn.microsoft.com/en-us/windows/ai/directml/pytorch-windows).

Não há promessa de extração em tempo real: `metadata.elapsed_seconds` registra
o experimento; `rss_mib_at_end` registra RAM residente ao final, não o pico.

## 2. Modelo-cobaia

| Modelo | Camadas / dimensão | Apenas pesos FP32, estimativa decimal | Uso |
|---|---:|---:|---|
| Pythia-70M | 6 / 512 | 0,28 GB | Testes pequenos, capacidade linguística limitada |
| **GPT-2 Small, 124M** | **12 / 768** | **0,50 GB** | **Implementado: primeiro experimento causal** |
| Qwen2.5-0.5B-Instruct | 24 / 896 | 1,96 GB | Próxima etapa: instruções e português |
| Qwen2.5-1.5B-Instruct | 28 / 1536 | cerca de 6,2 GB | Adiar: menos folga e varreduras caras |

Estimativa = parâmetros × quatro bytes, sem runtime, ativações e cópias.
GPT-2 é escolhido pela facilidade de dissecação e literatura sobre IOI; não por
raciocínio geral. Qwen 0.5B é um candidato posterior mais útil para instruções.
O adaptador atual é específico de GPT-2: trocar o ID do modelo não basta.
Llama-3.2-1B acrescenta licença própria/acesso condicionado sem vantagem inicial.

Fontes: [GPT-2](https://huggingface.co/openai-community/gpt2),
[Pythia](https://huggingface.co/EleutherAI/pythia-70m),
[Qwen 0.5B](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct),
[Qwen 1.5B](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct),
[Llama](https://huggingface.co/meta-llama/Llama-3.2-1B).

## 3. Arquitetura implementada

```text
lab/
  runtime.py    CPU, memória, download e carregamento do checkpoint fixado
  hooks.py      captura e substituição de saídas dos blocos
  patching.py   par de prompts, controles, varredura, scores JSON
  collect.py    cache limitado de UMA camada, corpus local por linha
  sae.py        dicionário esparso, treino, holdout, exemplos ativadores
  graphs.py     adaptador de resultados e exportação pelo Graphify instalado
tests/          controles com GPT-2 minúsculo, SAE sintético, exportador real
docs/AI-COLLABORATION.md   divisão de tarefas e revisão Antigravity
graphify-out/   graph.json, graph.html, GRAPH_REPORT.md do código
artifacts/      resultados experimentais e pesos SAE
```

Fluxo: `prompts → tokenizer → GPT-2 → hooks → patching.json → Graphify`.
Em separado: `corpus → hook de uma camada → sae-cache.pt → SAE → features candidatas`.
O Graphify mantém o grafo AST do repositório separado do grafo experimental.

Cache de todos os 12 blocos com 64 tokens: `12 × 64 × 768 × 4` = **2,25 MiB**,
sem pesos nem temporários. Para SAE, 8.192 tokens de uma camada = **24 MiB** de
vetores. O SAE 768→1536→768 tem cerca de 2,36 milhões de pesos; treinamento em
minibatches CPU mantém o custo pequeno em relação ao modelo. Esses cálculos não
representam a RAM total do processo.

O SAE usa ReLU, MSE normalizado + L1, centralização e escala ajustadas apenas no
treino, decoder com colunas de norma unitária e holdout por frase de origem.
Salva erro de reconstrução relativo ao baseline, L0 médio e fração de features
inativas no holdout. Exemplos exibem somente o prefixo visto pelo modelo, evitando
atribuir uma ativação a palavras futuras.

SAE não traduz automaticamente vetores em conceitos. `top_features.json` mantém
`semantic_label: null`; o pesquisador examina exemplos, contraexemplos e efeito
de intervenções. Poucos milhares de tokens servem para validar a engenharia,
não para afirmar que a superposição do GPT-2 foi resolvida.
[Superposição](https://www.transformer-circuits.pub/2022/toy_model/),
[SAEs](https://www.transformer-circuits.pub/2023/monosemantic-features/index.html).

O grafo experimental mostra normas observadas, conectividade **permitida** entre
blocos sob a máscara causal e nós de intervenção ligados à métrica. Não mostra
pesos de atenção medidos nem efeitos de arestas internas. Somente a relação
intervenção→métrica tem efeito medido. O HTML padrão do Graphify usa vis-network
por CDN: processamento local, visualização requer internet para carregar esse JS.

Um Circuit Attribution Graph em nível de features requer trabalho adicional:
SAEs/transcoders adequados, atribuição entre features e avaliação da fidelidade do
modelo substituto, seguida de intervenções. Não se obtém isso apenas convertendo
uma matriz em nós/arestas. [Método de circuit tracing](https://www.transformer-circuits.pub/2025/attribution-graphs/methods.html).

## 4. Primeiro experimento no PowerShell

Na raiz deste repositório, use diretamente o Python do venv; não precisa ativá-lo
nem alterar a política de execução do Windows. Dependências já instaladas nesta
máquina podem ser verificadas com os testes. Para reconstruir o ambiente:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv/Scripts/python.exe transformers==4.57.6 psutil==7.2.2
```

Preparar o modelo e verificar a memória:

```powershell
.venv/Scripts/python.exe -X utf8 -m lab.runtime --download
.venv/Scripts/python.exe -X utf8 -m lab.runtime
```

O download inicial usa internet; com os seis arquivos em cache a carga não
precisa consultar o Hub. O modelo roda localmente. Se houver menos de
3 GiB disponíveis, liberar memória de aplicativos e repetir. O programa não fecha
aplicativos do usuário nem contorna essa proteção.

Executar primeiro a varredura curta (posição alterada e posição final):

```powershell
.venv/Scripts/python.exe -X utf8 -m lab.patching
.venv/Scripts/python.exe -X utf8 -m lab.graphs --results artifacts/patching.json --output artifacts/circuit --graphify-python C:/Python314/python.exe
Invoke-Item artifacts/circuit/graph.html
```

Prompts usados, com nomes de token único:

- Limpo: `When John and Mary went to the shops, John gave the bag to`
- Corrompido: `When John and Mary went to the shops, Mary gave the bag to`
- Métrica: `D = logit(" Mary") − logit(" John")` no próximo token.

Esperamos D positivo no limpo e negativo no corrompido; o código registra se isso
aconteceu. Para cada bloco/posição, substitui o residual corrompido pelo limpo e
mede `efeito = D_patch − D_corrompido`. Recuperação = efeito dividido por
`D_limpo − D_corrompido`; denominador quase zero resulta em `null`. Recuperação
pode ser negativa ou maior que 1, sem truncamento.

Controles obrigatórios executados antes da varredura:

1. Corrompido→corrompido e limpo→limpo: alteração menor que 1e-4.
2. Último bloco, última posição, limpo→corrompido: restaura a métrica limpa.
3. Último bloco, posição anterior: efeito nulo na previsão final, pois não resta
   atenção para transportar informação entre posições.

A restauração final valida a implementação, mas não localiza por si só um
mecanismo interessante. Procurar efeitos nas **camadas intermediárias**, repetir
em nomes/templates novos e comparar controles. Exemplo de replicação independente:

```powershell
.venv/Scripts/python.exe -X utf8 -m lab.patching --clean "When Alice and Bob went to the park, Alice gave a book to" --corrupt "When Alice and Bob went to the park, Bob gave a book to" --target Bob --contrast Alice --output artifacts/holdout.json
```

Para todas as posições de todos os blocos, em saída separada:

```powershell
.venv/Scripts/python.exe -X utf8 -m lab.patching --positions all --output artifacts/full.json
.venv/Scripts/python.exe -X utf8 -m lab.graphs --results artifacts/full.json --output artifacts/full-circuit --graphify-python C:/Python314/python.exe
```

Cada execução investiga o próximo token de um contexto fixo. Investigar uma
resposta inteira exige repetir por prefixo/token com contrafactuais alinhados;
essa automação ainda não faz parte desta versão.

## SAE e mapa do repositório

Crie `corpus.txt` UTF-8 com centenas de frases variadas, uma por linha; inglês é
adequado ao GPT-2 inicial. Não use só o par IOI para interpretar features.

```powershell
.venv/Scripts/python.exe -X utf8 -m lab.collect --corpus corpus.txt --layer 7 --max-tokens 8192
.venv/Scripts/python.exe -X utf8 -m lab.sae --cache artifacts/sae-cache.pt --output artifacts/sae --steps 200 --features 1536
.venv/Scripts/python.exe -X utf8 -m lab.graphs --repo --graphify-python C:/Python314/python.exe
Invoke-Item graphify-out/graph.html
```

A camada 7 é indexada a partir de zero. O checkpoint SAE contém normalização,
pesos e identificação do modelo/camada. Não é um SAE pré-treinado validado.
Não há feature steering implementado nesta etapa; o experimento causal inicial é
activation patching. Pontos de extensão futuros: cabeças/MLPs, ablação de features,
teste de reconstrução sobre logits e transcoders. Primeiro medir a qualidade.

Validar a implementação, sem baixar modelo para os testes:

```powershell
$env:GRAPHIFY_PYTHON = 'C:/Python314/python.exe'
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
```

Graphify usa exclusivamente os fontes de `lab/`, sem varrer venv/modelos. A
extração AST é determinística, sem chamadas LLM nem tokens de extração. O trabalho
de revisão Antigravity/Codex é separado desse custo. Consulte `GRAPH_REPORT.md`
para comunidades, coesão e integridade. Resultados gerados são ignorados pelo Git;
os fontes e instruções permanecem versionáveis.
