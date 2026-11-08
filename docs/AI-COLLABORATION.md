# Orquestração deste laboratório

Codex integra e testa os arquivos. Antigravity/Argon revisa a arquitetura por meio
do helper da skill `orquestrar-antigravity`, com login já gerenciado pelo produto.
O cálculo do modelo e o treino do SAE acontecem localmente; a revisão pelo agente
Antigravity utiliza um modelo remoto. Não enviar corpus privado sem autorização.

Revisão executada com recibo verificado: `gemini-4-argon-high`, modo `plan`,
status `SUCCESS`, resposta não vazia, nenhuma ferramenta chamada. O briefing
ficou em diretório temporário mínimo, sem credenciais, corpus ou histórico Git.
Os registros completos permanecem privados fora do repositório.

Etapas e escopo:

1. Pesquisa de compatibilidade Intel e escolha de modelo: fontes oficiais.
2. Antigravity: revisão de arquitetura e critérios de validação.
3. Implementação modular: runtime/hooks/patching/coleta; SAE; adaptador Graphify.
4. Integração: testes CPU, exportação Graphify real e controles de intervenções.
5. Execução com GPT-2 condicionada a memória livre; registrar resultados reais.

Pontos da revisão incorporados: preservar tupla da saída de GPT2Block; validar
tokenização e alinhamento; controlar identidade, restauração final e efeito nulo
em posição anterior do último bloco; normalizar decoder; não treinar um SAE como
se duas frases fossem um corpus representativo; separar AST e dados experimentais.

Afirmações da revisão que **não** foram adotadas: garantia de processo <1,2 GB;
garantia de que quatro threads fiquem nos P-cores; metas arbitrárias de qualidade
do SAE como prova de conceitos. RAM, latência e qualidade precisam ser medidas.

Arquivos de execução são exclusivamente `lab/`; testes em `tests/`; resultados
em `artifacts/`; grafo AST em `graphify-out/`. Não editar os mesmos arquivos por
dois executores simultâneos. Graphify usa o Python 3.14 já instalado; PyTorch
fica no venv Python 3.11 para evitar misturar dependências globais.

Interface visual: usuário confirmou painel no navegador local. Codex integrou
HTML/CSS/JS; um executor separado implementou servidor/API e seus testes. Nova
revisão Antigravity/Argon concluída em modo plan, mesmo modelo, SUCCESS e nenhuma
ferramenta chamada. Foram incorporados: Host/Origin estritos, argumentos CLI no
formato `--campo=valor`, fila única, limites de memória/log, demonstração explícita
não persistida e isolamento dos grafos em iframes. A revisão analisou o plano,
não executou o programa. A integração foi validada separadamente no navegador.

Caso público IOI. Antigravity revisou o plano em modo `plan` com
`gemini-4-argon-high`. O recibo retornou `SUCCESS`, com resposta e zero chamadas
de ferramentas. A página incorpora a comparação com o token vizinho, a distinção
entre medições registradas e inferência e a verificação de caminhos relativos no
subdiretório do projeto. A conclusão foi delimitada à dependência observada entre
estados inteiros nos pares testados. A reprodução e os testes ficaram com o Codex.

Installed lab. Antigravity reviewed the English onboarding and Windows install
plan in `plan` mode with `gemini-4-argon-high`. The receipt returned `SUCCESS`
with a response and zero tool calls. The implementation distinguishes measured
replay from local inference, documents GPT‑2 token constraints, and keeps the
measurement export available when Graphify is missing or fails. The dependency
and checkpoint pins were retained. Installation and runtime checks were separate
from the Antigravity review.
