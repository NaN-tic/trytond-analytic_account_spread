#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateView, Button
from trytond.exceptions import UserError
from trytond.i18n import gettext

__all__ = ['SpreadAsk', 'SpreadAskLine', 'SpreadWizard', 'MoveLine']
ZERO = Decimal(0)

class SpreadAskLine(ModelView):
    'Spread Analytic Lines Ask Line'
    __name__ = 'analytic_account.line.spread.ask.line'
    ask = fields.Many2One('analytic_account.line.spread.ask',
        'Ask Wizard')
    root = fields.Many2One('analytic_account.account', 'Root Account',
        required=True,
        domain=[
            ('type', '=', 'root'),
            ['OR',
                ('company', '=', None),
                ('company', '=', Eval('company', -1)),
                ],
            ],
        depends=['company'])
    account = fields.Many2One('analytic_account.account', 'Account',
        required=True,
        domain=[
            ('root', '=', Eval('root', 0)),
            ('type', 'not in', ['view', 'root']),
            ['OR',
                ('company', '=', None),
                ('company', '=', Eval('company', -1)),
                ],
            ],
        depends=['company', 'root'])
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])

    @staticmethod
    def default_amount():
        return Transaction().context.get('pending_amount')

    @fields.depends('ask')
    def on_change_with_company(self, name=None):
        if self.ask:
            return self.ask.company.id

    @fields.depends('ask')
    def on_change_with_currency_digits(self, name=None):
        if self.ask:
            return self.ask.currency_digits
        return 2

    def get_analytic_line(self, defaults):
        pool = Pool()
        Line = pool.get('analytic_account.line')
        line = Line()
        for key, value in defaults.items():
            setattr(line, key, value)

        line.name = self.account.rec_name
        line.account = self.account
        if self.amount > ZERO:
            line.credit = self.amount
            line.debit = ZERO
        else:
            line.debit = abs(self.amount)
            line.credit = ZERO
        return line


class SpreadAsk(ModelView):
    'Spread Analytic Lines Ask'
    __name__ = 'analytic_account.line.spread.ask'

    move_line = fields.Many2One('account.move.line', 'Account Move Line',
            ondelete='CASCADE', required=True)
    currency = fields.Function(fields.Many2One('currency.currency',
            'Currency'), 'on_change_with_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company')
    roots = fields.One2Many('analytic_account.account', None, 'Root Accounts',
        required=True,
        domain=[
            ('type', '=', 'root'),
            ['OR',
                ('company', '=', None),
                ('company', '=', Eval('company', -1)),
                ],
            ],
        depends=['company'])
    root = fields.Many2One('analytic_account.account', 'Root Account',
        required=True, readonly=True,
        domain=[
            ('type', '=', 'root'),
            ['OR',
                ('company', '=', None),
                ('company', '=', Eval('company', -1)),
                ],
            ],
        depends=['company'])
    amount = fields.Numeric('Amount', readonly=True,
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    pending_amount = fields.Function(fields.Numeric('Pending Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'on_change_with_pending_amount')
    lines = fields.One2Many('analytic_account.line.spread.ask.line',
        'ask', 'Lines',
        context={
            'pending_amount': Eval('pending_amount'),
            },
        domain=[
            ('root', '=', Eval('root', 0)),
            ],
        depends=['root', 'pending_amount'])

    @fields.depends('move_line')
    def on_change_with_company(self, name=None):
        if self.move_line:
            return self.move_line.account.company.id

    @fields.depends('move_line')
    def on_change_with_currency(self, name=None):
        if self.move_line:
            return self.move_line.account.company.currency.id

    @fields.depends('move_line')
    def on_change_with_currency_digits(self, name=None):
        if self.move_line:
            return self.move_line.account.company.currency.digits
        return 2

    @fields.depends('lines', 'amount', 'currency')
    def on_change_with_pending_amount(self, name=None):
        lines_amount = sum((l.amount or ZERO for l in self.lines), ZERO)
        amount = (self.amount or ZERO) - lines_amount
        if self.currency:
            amount = self.currency.round(amount)
        return amount


class SpreadWizard(Wizard):
    'Spread Analytic Lines Wizard'
    __name__ = 'analytic_account.line.spread'
    start_state = 'next_'
    next_ = StateTransition()
    ask = StateView('analytic_account.line.spread.ask',
        'analytic_account_spread.spread_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Skip', 'next_', 'tryton-go-next'),
            Button('Spread', 'spread', 'tryton-ok', default=True),
            ])
    spread = StateTransition()

    def get_roots(self):
        'Return a list of roots to spread'
        pool = Pool()
        Account = pool.get('analytic_account.account')
        return [a.id for a in Account.search([
                    ('company', '=', self.ask.company.id),
                    ('type', '=', 'root'),
                    ])]

    def transition_next_(self):
        pool = Pool()
        MoveLine = pool.get('account.move.line')

        def next_root():
            roots = list(self.ask.roots)
            if not roots:
                return
            root = roots.pop()
            self.ask.root = root
            self.ask.roots = roots
            return root

        if getattr(self.ask, 'move_line', None) is None:
            move_line = MoveLine(Transaction().context.get('active_id'))
            self.ask.move_line = move_line
            company = move_line.account.company
            self.ask.company = company
            self.ask.currency = company.currency
            self.ask.amount = company.currency.round(
                move_line.credit - move_line.debit)
            self.ask.currency_digits = company.currency.digits

        if getattr(self.ask, 'roots', None) is None:
            self.ask.roots = self.get_roots()

        if next_root():
            return 'ask'
        return 'end'

    def default_ask(self, fields):
        defaults = {}
        defaults['move_line'] = self.ask.move_line.id
        defaults['roots'] = [a.id for a in self.ask.roots]
        defaults['root'] = self.ask.root.id
        defaults['company'] = self.ask.company.id
        defaults['currency'] = self.ask.currency.id
        defaults['currency_digits'] = self.ask.currency.digits
        defaults['amount'] = self.ask.amount
        defaults['lines'] = self._default_lines()
        defaults['pending_amount'] = self.ask.on_change_with_pending_amount()
        return defaults

    def _default_lines(self):
        'Return the lines to spreed the amount (if one)'
        default = []
        for line in self.ask.move_line.analytic_lines:
            if line.account.root != self.ask.root:
                continue
            default.append({
                    'root': line.account.root.id,
                    'account': line.account.id,
                    'ask': self.ask.id,
                    'currency_digits': self.ask.currency_digits,
                    'amount': line.credit - line.debit,
                    })
        return default

    def transition_spread(self):
        pool = Pool()
        Line = pool.get('analytic_account.line')

        if self.ask.pending_amount != 0:
            raise UserError(gettext(
                    'analytic_account_spread.msg_incorrect_spreading',
                    amount=self.ask.pending_amount))

        linesbyaccount = dict((l.account, l) for l
            in self.ask.move_line.analytic_lines)
        to_create, to_write = [], []
        line_defaults = {
            'move_line': self.ask.move_line,
            'date': self.ask.move_line.date,
            'party': self.ask.move_line.party,
            }
        for value in self.ask.lines:
            if value.account in linesbyaccount:
                line = linesbyaccount.pop(value.account)
                line_amount = line.credit - line.debit
                if value.amount != line_amount:
                    if value.amount > ZERO:
                        line.credit = value.amount
                        line.debit = ZERO
                    else:
                        line.debit = abs(value.amount)
                        line.credit = ZERO
                    to_write.extend(([line], line._save_values))
            else:
                line = value.get_analytic_line(line_defaults)
                if line:
                    to_create.append(line._save_values)
        if to_create:
            Line.create(to_create)
        if to_write:
            Line.write(*to_write)
        if linesbyaccount:
            Line.delete(linesbyaccount.values())
        return 'next_'


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @classmethod
    def __setup__(cls):
        super(MoveLine, cls).__setup__()
        cls._buttons.update({
                'spread_analytic': {}
                })

    @classmethod
    @ModelView.button_action('analytic_account_spread.spread_wizard')
    def spread_analytic(cls, lines):
        pass
