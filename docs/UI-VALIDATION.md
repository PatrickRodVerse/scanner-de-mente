# Interface local — verificação em 31/10/2026

Interface HTML/CSS/JavaScript e servidor da biblioteca padrão Python. Não há nova
dependência Python nem npm. Fontes IBM Plex locais: cerca de 74 KiB no total,
com licenças OFL incluídas.

Verificações realizadas:

- Testes HTTP da interface: estado, arquivos permitidos, exportação, composição
  dos comandos, fila ocupada, erro preservando resultado anterior, limite de RAM,
  atualização por resultado criado no terminal, grafo desatualizado, reabertura
  do painel existente e importação sem carregar torch.
- Host/Origin/Content-Type inválidos, limites JSON e tentativas de traversal
  rejeitados. Após corrigir um reset de conexão no Windows, os testes de rejeição
  de origem e payload foram repetidos dez vezes cada e passaram.
- Self-check Node: demonstração sintética, consistência efeito/score/recuperação,
  controles estruturais e escala de cor com valores negativos/ausentes.
- Navegador Chrome real: 168 células sintéticas, seleção por clique/setas, troca
  de métrica, saída do modo demo, vistas SAE/Graphify e nenhuma exceção JavaScript.
- Mobile 390px: navegação permanece aberta durante polling, fecha ao selecionar
  a vista atual e não há transbordamento horizontal no documento. A matriz tem
  rolagem própria.
- Atualização Graphify real por botão: tarefa concluída, grafo com 76 nós e
  138 arestas naquele teste; iframe recarregado com o ID da tarefa concluída.
- Inspeção responsiva 1440/768/390: zero FAIL. Dois avisos aceitos: rótulos de
  coordenadas/metadados de 11–12px e ausência de cor de dados no estado inicial
  sem medições. O mapa ganha cor apenas com resultados ou demonstração explícita.

Capturas inspecionadas em `.taste-skill/browser/` e `.taste-skill/inspect-final/`,
ignoradas pelo Git. Direção framed-sheet, seed 907720188, sem redesenhos; tokens
e decisões em DESIGN.md. O painel principal não depende de CDN; os grafos Graphify
mantêm a dependência de vis-network em iframe isolado.

Não executado: GPT-2 pré-treinado pela interface (RAM livre abaixo da margem de
3 GiB) e SAE em corpus real. A tela SAE exibe métricas existentes; coleta e treino
continuam disponíveis pelos comandos Python documentados. A demonstração não foi
salva como resultado experimental.
