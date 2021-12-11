# KnowledgeBaseBot

## Instalowanie TypeDB

1. [Pobrać](https://vaticle.com/download) i rozpakować TypeDB
2. W rozpakowanym katalogu `./typedb server`
3. W oddzielnym terminalu `./typedb console`
   1. `database create events`
   2. `transaction events schema write`
   3. `source <bezwględna ścieżka do knowledge_base/schema-demo.tql>`
   4. `commit`
   5. Ctrl-D
4. Potem `./typedb console --script="/home/wojtekk23/Projekty/Calmsie/KnowledgeBaseBot/knowledge_base/schema-demo-insert.tql"`

## Uruchomienie czatbota

1. `rasa shell`
2. `rasa run actions`

## Przykładowa rozmowa

* Wymień osoby
* Jaka jest płeć drugiej osoby?
* Wymień wydarzenia
* Gdzie odbywa się pierwsze wydarzenie?