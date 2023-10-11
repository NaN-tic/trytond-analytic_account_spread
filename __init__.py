# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import line


def register():
    Pool.register(
        line.SpreadAsk,
        line.SpreadAskLine,
        line.MoveLine,
        module='analytic_account_spread', type_='model')
    Pool.register(
        line.SpreadWizard,
        module='analytic_account_spread', type_='wizard')
