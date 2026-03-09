# container_runner package
#
# Módulo de comunicação entre containers de tarefas e o orquestrador.
#
# Componentes:
#   channel.py  → usado DENTRO do container de tarefa (emite JSON para stdout)
#   runner.py   → usado pelo ORQUESTRADOR (lança container, captura logs, persiste)
#   config.py   → ContainerJobConfig + make_container_callable
