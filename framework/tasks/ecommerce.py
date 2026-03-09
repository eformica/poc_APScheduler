"""
Tarefas do domínio de E-commerce.

Cada método representa um job independente registrado em scheduler/registry.py.
Erros são intencionalmente lançados em alguns casos para demonstrar
o logging automático de falhas no PostgreSQL.
"""

import random

from tasks.base import BaseTask


class EcommerceTask(BaseTask):

    def processar_pedidos(self) -> None:
        """
        Processa pedidos pendentes na fila de pagamentos.
        Produção: IntervalTrigger(minutes=5)
        """
        qtd = random.randint(0, 50)
        valor_total = qtd * random.uniform(50.0, 500.0)

        # Simula falha de gateway de pagamento (5% de chance)
        if random.random() < 0.05:
            raise ConnectionError(
                "Timeout ao conectar com o gateway de pagamento (> 5 s)"
            )

        if qtd:
            self.logger.info(
                f"✅ {qtd} pedido(s) processado(s) | total: R$ {valor_total:,.2f}"
            )
        else:
            self.logger.info("✅ Nenhum pedido pendente na fila")

    def verificar_estoque(self) -> None:
        """
        Verifica SKUs abaixo do estoque mínimo e dispara alertas de reposição.
        Produção: IntervalTrigger(minutes=15)
        """
        abaixo_minimo = random.randint(0, 5)

        if abaixo_minimo:
            self.logger.warning(
                f"⚠️  {abaixo_minimo} SKU(s) abaixo do estoque mínimo — "
                "notificando equipe de compras"
            )
        else:
            self.logger.info("✅ Todos os SKUs com estoque adequado")

    def exportar_relatorio_vendas(self) -> None:
        """
        Exporta relatório de vendas do período para CSV/S3.
        Produção: CronTrigger(hour=8, minute=0)
        """
        linhas = random.randint(200, 5_000)
        arquivo = f"relatorio_vendas_{random.randint(1000, 9999)}.csv"

        # Simula falha de escrita em disco (8% de chance)
        if random.random() < 0.08:
            raise OSError(
                f"Falha ao gravar '{arquivo}': espaço insuficiente em disco"
            )

        self.logger.info(
            f"✅ Relatório exportado: {arquivo} ({linhas} linhas)"
        )
