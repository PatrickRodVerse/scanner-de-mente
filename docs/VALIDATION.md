# Validação local — 31/10/2026

- Ambiente instalado: Python 3.11.15, torch 2.10.0+cpu, transformers 4.57.6,
  psutil 7.2.2, Windows x64. CPU detectada: Core Ultra 5 125U, 12 núcleos e
  14 processadores lógicos. RAM física reportada: 16.597.598.208 bytes.
- Antigravity: revisão concluída, modelo solicitado/retornado
  `gemini-4-argon-high`, modo plan, status SUCCESS, nenhuma ferramenta chamada.
- Dez testes automatizados passaram: hook e restauração em GPT-2 minúsculo
  inicializado aleatoriamente, remoção de hooks em exceções, recuperação assinada,
  limites de memória/cache, normalização e treino SAE sintético determinístico,
  separação de frases no holdout e exportação Graphify real.
- Checkpoint GPT-2 baixado: revisão `607a30d783dfa663caf39e06633721c8d4cfcd7e`.
  `model.safetensors`: 548.105.171 bytes, mais cinco arquivos pequenos de
  configuração/tokenização. Cache completo pode ser usado sem consultar o Hub.
- Tentativa do experimento pré-treinado: interrompida antes de carregar o modelo,
  pois havia 2,57 GiB livres e o mínimo é 3 GiB. Amostras posteriores de RAM livre
  variaram; não são um benchmark. **Não existe resultado IOI medido no GPT-2**.
- Grafo Graphify real produzido para `lab/`: HTML, JSON, relatório e diagnóstico.
  Extração AST determinística: zero tokens LLM. O relatório registra contagens
  atuais, hubs e relações entre módulos.

Limites detectados no grafo AST bruto: 24 relações para importações externas sem
nós correspondentes; cinco pares com relações diferentes que o DiGraph colapsa;
uma autoligação de `super().__init__` resolvida pelo extrator como o próprio
construtor. Não interpretar essa autoligação como recursão. O AST é um mapa parcial,
não uma garantia exaustiva do fluxo em execução. A extração bruta e os diagnósticos
permanecem preservados para auditoria. O grafo de intervenções sintéticas passou
nos testes de integridade e preservação do sinal do efeito.

Não validados: latência/pico de RAM com GPT-2 pré-treinado, iGPU/XPU, NPU,
DirectML, OpenVINO, SAE em corpus real, circuitos por cabeça/feature e inspeção
visual do HTML em navegador. O HTML padrão requer o JavaScript vis-network da CDN.
