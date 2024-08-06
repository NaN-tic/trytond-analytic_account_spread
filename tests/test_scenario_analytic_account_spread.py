import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear,
                                                 get_accounts)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install account
        activate_modules('analytic_account_spread')

        # Create company
        _ = create_company()
        company = get_company()

        # Create fiscal year
        fiscalyear = create_fiscalyear(company)
        fiscalyear.click('create_period')
        period = fiscalyear.periods[0]

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        receivable = accounts['receivable']
        revenue = accounts['revenue']

        # Create analytic accounts
        AnalyticAccount = Model.get('analytic_account.account')
        root = AnalyticAccount(type='root', name='Root')
        root.save()
        analytic_account = AnalyticAccount(root=root,
                                           parent=root,
                                           name='Analytic')
        analytic_account.save()
        other_analytic_account = AnalyticAccount(root=root,
                                                 parent=root,
                                                 name='Other Analytic')
        other_analytic_account.save()

        # Create parties
        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.save()

        # Create Move
        Journal = Model.get('account.journal')
        Move = Model.get('account.move')
        journal_revenue, = Journal.find([
            ('code', '=', 'REV'),
        ])
        journal_cash, = Journal.find([
            ('code', '=', 'CASH'),
        ])
        move = Move()
        move.period = period
        move.journal = journal_revenue
        move.date = period.start_date
        line = move.lines.new()
        line.account = revenue
        line.credit = Decimal(42)
        line = move.lines.new()
        line.account = receivable
        line.debit = Decimal(42)
        line.party = customer
        move.save()
        revenue_line, = [l for l in move.lines if l.account == revenue]

        # Open the spread wizard
        self.assertEqual(len(revenue_line.analytic_lines), 0)
        spread = Wizard('analytic_account.line.spread', [revenue_line])
        self.assertEqual(spread.form.root, root)
        self.assertEqual(spread.form.amount, Decimal('42.00'))
        self.assertEqual(spread.form.pending_amount, Decimal('42.00'))
        self.assertEqual(len(spread.form.lines), 0)
        line = spread.form.lines.new()
        line.account = analytic_account
        self.assertEqual(line.amount, Decimal('42.00'))
        line.amount = Decimal(21)
        line = spread.form.lines.new()
        line.account = other_analytic_account
        self.assertEqual(line.amount, Decimal('21.00'))
        self.assertEqual(spread.form.pending_amount, Decimal('0.00'))
        spread.execute('spread')
        revenue_line.reload()
        self.assertEqual(len(revenue_line.analytic_lines), 2)
