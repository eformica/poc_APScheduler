#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║         POC APScheduler — Agendador de Tarefas               ║
║         APScheduler 3.x | Python 3.13+                       ║
╚══════════════════════════════════════════════════════════════╝

Demonstração das principais funcionalidades do APScheduler
com exemplos práticos de casos de uso reais.

Exemplos disponíveis:
  1. IntervalTrigger  — Tarefas em intervalos regulares
  2. CronTrigger      — Agendamento estilo cron (horários fixos)
  3. DateTrigger      — Execução única em data/hora específica
  4. Gerenciamento    — Pausar, retomar, modificar e remover jobs
  5. Casos Reais      — E-commerce, Analytics, DevOps, Financeiro
  6. Persistência     — Jobs salvos em banco SQLite (sobrevivem restart)

Instalação:
  uv sync   ou   pip install apscheduler sqlalchemy
"""

import sys
import os
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MENU = [
    ("1", "IntervalTrigger ", "Intervalos regulares (monitor, sync, heartbeat)"),
    ("2", "CronTrigger     ", "Horários fixos (relatório diário, backup noturno)"),
    ("3", "DateTrigger     ", "Execução única (notificações, publicações)"),
    ("4", "Gerenciamento   ", "Pausar, retomar, modificar, remover jobs"),
    ("5", "Casos Reais     ", "E-commerce, Analytics, DevOps, Financeiro"),
    ("6", "Persistência    ", "Jobs em SQLite com event listeners"),
]

HANDLERS = {
    "1": "examples.interval_trigger",
    "2": "examples.cron_trigger",
    "3": "examples.date_trigger",
    "4": "examples.job_management",
    "5": "examples.real_world_cases",
    "6": "examples.persistent_jobs",
}


def display_menu() -> None:
    print("\n" + "═" * 64)
    print("   POC APScheduler — Agendador de Tarefas")
    print("═" * 64)
    print("  Escolha um exemplo:\n")
    for key, name, description in MENU:
        print(f"  [{key}] {name}  {description}")
    print("\n  [0] Sair")
    print("═" * 64)


def main() -> None:
    while True:
        display_menu()
        choice = input("\n  Opção: ").strip()

        if choice == "0":
            print("\n  Até mais!\n")
            sys.exit(0)

        if choice not in HANDLERS:
            print("\n  Opção inválida. Tente novamente.")
            continue

        try:
            module = importlib.import_module(HANDLERS[choice])
            module.run()
        except KeyboardInterrupt:
            print("\n\n  Execução interrompida pelo usuário.")
        except ImportError as exc:
            print(f"\n  Erro ao importar módulo: {exc}")
            print("  Execute:  uv sync   ou   pip install apscheduler sqlalchemy")


if __name__ == "__main__":
    main()

