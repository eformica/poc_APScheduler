"""
Tarefas do domínio de DevOps / Infraestrutura.

Cada método representa um job independente registrado em scheduler/registry.py.
"""

import random

from tasks.base import BaseTask


class DevOpsTask(BaseTask):

    SERVICOS = ["API Gateway", "Auth Service", "Payment API", "DB Primary", "Cache Redis"]

    def health_check(self) -> None:
        """
        Verifica a disponibilidade e latência dos serviços críticos.
        Produção: IntervalTrigger(seconds=30)
        """
        # Simula falha de serviço (10% de chance)
        if random.random() < 0.10:
            servico = random.choice(self.SERVICOS)
            raise TimeoutError(
                f"Health check timeout: '{servico}' não respondeu em 5 s — "
                "acionando plantão on-call"
            )

        latencias = {s: random.randint(5, 120) for s in self.SERVICOS}
        resumo = " | ".join(f"{s}: {ms}ms" for s, ms in latencias.items())
        self.logger.info(f"✅ Todos os serviços OK — {resumo}")

    def limpar_temporarios(self) -> None:
        """
        Remove arquivos temporários e logs antigos do servidor.
        Produção: CronTrigger(hour='*/4')
        """
        arquivos = random.randint(20, 500)
        mb       = random.randint(50, 2_000)
        self.logger.info(
            f"✅ Limpeza concluída: {arquivos} arquivo(s) removido(s) "
            f"({mb} MB liberados)"
        )

    def verificar_certificados_ssl(self) -> None:
        """
        Verifica a validade dos certificados SSL em todos os domínios.
        Produção: IntervalTrigger(hours=6)
        """
        a_expirar = random.randint(0, 2)
        if a_expirar:
            self.logger.warning(
                f"⚠️  {a_expirar} certificado(s) expira(m) em menos de 30 dias — "
                "renovação automática agendada"
            )
        else:
            self.logger.info(
                f"✅ {len(self.SERVICOS)} certificados SSL válidos"
            )
