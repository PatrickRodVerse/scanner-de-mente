# Interface do laboratório local

Modo Operate: o pesquisador inicia um protocolo e examina onde a substituição do
residual muda a preferência entre nomes. O mapa camada × token é a região principal;
o inspetor à direita mostra a intervenção selecionada, unidades e comparação.

Direção `framed-sheet`, seed 907720188, sem redesenhos do sorteio. Frame cinza com
um leve tom de instrumentação, folha branca, separação por linhas e sem sombras.
IBM Plex Sans para a interface, IBM Plex Mono para tokens/código. Fontes locais
com licenças OFL incluídas. Um mapa divergente teal/âmbar codifica o sinal do efeito;
o estado de memória tem texto além da cor. Não usar animação decorativa.

Tokens em `ui/style.css`: ground #f1f5f5, surface #ffffff, ink #182527,
muted #566769, accent/data positivo #1b6c80, data negativo #a86f3f,
border #e2e8e8, gap 24px, sidebar 228px, sheet radius 16px, panel radius 8px,
control radius 6px. Título 26px, seção 15px, texto 14px, metadados 11–12px.

Três vistas: experimento; métricas e prefixos do SAE; grafo do código. Sem resultado,
o mapa preserva a estrutura e oferece executar ou ativar uma demonstração explícita.
Seleção de célula por clique ou setas. Estado de demonstração temporário e sem
exportação. Gráficos Graphify ficam em iframes isolados; seus scripts CDN não são
necessários para operar o painel principal.

No celular, navegação recolhida, contextos empilhados e matriz com rolagem própria;
o documento não deve transbordar horizontalmente. Foco visível e redução de movimento
respeitada. Polling não deve fechar o menu nem deslocar o foco.
