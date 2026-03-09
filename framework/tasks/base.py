"""
Classe base para todas as tarefas agendadas.

Convenções:
  - Cada classe de tarefa herda de BaseTask.
  - Cada método público é uma tarefa independente registrável no scheduler.
  - Métodos devem ser autocontidos: recebem, processam e retornam sem estado
    compartilhado entre execuções (thread-safe por design).
  - Erros esperados devem ser lançados como exceções Python — o wrapper
    make_logged_callable() em execution_logger.py os captura e persiste.
  - Use self.logger para emitir mensagens; NÃO use print().
"""

import logging
from abc import ABC


class BaseTask(ABC):
    """
    Classe base abstrata para tarefas agendadas.
    Fornece um logger pré-configurado com o nome da subclasse.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
