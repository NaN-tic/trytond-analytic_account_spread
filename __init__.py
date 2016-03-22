# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .line import *


def register():
    Pool.register(
        SpreadAsk,
        SpreadAskLine,
        MoveLine,
        module='analytic_account_spread', type_='model')
    Pool.register(
        SpreadWizard,
        module='analytic_account_spread', type_='wizard')
