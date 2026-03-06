from odoo import api, exceptions, fields, models


class SfkQualityTemplate(models.Model):
    _name = "sfk.quality.template"
    _description = "Quality Assessment Template"
    _order = "role_type, target_type, name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    role_type = fields.Selection(
        [
            ('instructor', 'Instructor'),
            ('supervisor', 'Supervisor'),
            ('coach_manager', 'Coach Manager'),
        ],
        required=True,
    )
    target_type = fields.Selection(
        [('session', 'Session'), ('program', 'Program')],
        required=True,
        default='session',
    )
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    question_ids = fields.One2many('sfk.quality.template.question', 'template_id', string='Questions')


class SfkQualityTemplateQuestion(models.Model):
    _name = "sfk.quality.template.question"
    _description = "Quality Template Question"
    _order = "sequence, id"

    template_id = fields.Many2one('sfk.quality.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    question = fields.Text(required=True)
    answer_type = fields.Selection(
        [('text', 'Text'), ('score', 'Score'), ('selection', 'Selection')],
        default='text',
        required=True,
    )
    required = fields.Boolean(default=True)
    max_score = fields.Float(default=5.0)
    options = fields.Char(help='Comma-separated options when answer type is Selection.')


class SfkQualityRequest(models.Model):
    _name = "sfk.quality.request"
    _description = "Quality Report Request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"

    name = fields.Char(required=True, default='New Quality Request', tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('requested', 'Requested'), ('done', 'Done'), ('cancelled', 'Cancelled')],
        default='draft',
        tracking=True,
    )
    request_type = fields.Selection([('session', 'Session'), ('program', 'Program')], required=True, default='session')
    session_id = fields.Many2one('sfk.session', tracking=True)
    program_id = fields.Many2one('sfk.program', tracking=True)
    requested_to_role = fields.Selection(
        [('instructor', 'Instructor'), ('supervisor', 'Supervisor'), ('coach_manager', 'Coach Manager')],
        required=True,
        tracking=True,
    )
    review_period = fields.Selection([('monthly', 'Monthly'), ('term', 'Term'), ('custom', 'Custom')], default='custom')
    term_id = fields.Many2one('sfk.term', string='Term')
    period_start = fields.Date()
    period_end = fields.Date()
    deadline = fields.Date(tracking=True)
    notes = fields.Text()
    requested_by = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    assessment_ids = fields.One2many('sfk.quality.assessment', 'request_id')
    assessment_count = fields.Integer(compute='_compute_assessment_count')

    @api.depends('assessment_ids')
    def _compute_assessment_count(self):
        for rec in self:
            rec.assessment_count = len(rec.assessment_ids)

    def action_request(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_manager'):
            raise exceptions.AccessError('Only Operation Managers can request quality reports.')
        for rec in self:
            if rec.request_type == 'session' and not rec.session_id:
                raise exceptions.ValidationError('Session is required for session-level requests.')
            if rec.request_type == 'program' and not rec.program_id:
                raise exceptions.ValidationError('Program is required for program-level requests.')
            rec.state = 'requested'

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class SfkQualityAssessment(models.Model):
    _name = "sfk.quality.assessment"
    _description = "Quality Assessment"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"

    name = fields.Char(required=True, default='New Assessment', tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='draft',
        tracking=True,
    )
    template_id = fields.Many2one('sfk.quality.template', required=True)
    template_role_type = fields.Selection(related='template_id.role_type', store=True)
    target_type = fields.Selection([('session', 'Session'), ('program', 'Program')], required=True, default='session', tracking=True)
    session_id = fields.Many2one('sfk.session', tracking=True)
    program_id = fields.Many2one('sfk.program', tracking=True)
    request_id = fields.Many2one('sfk.quality.request', tracking=True)
    assessor_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True, tracking=True)
    assessor_role = fields.Selection(
        [('instructor', 'Instructor'), ('supervisor', 'Supervisor'), ('coach_manager', 'Coach Manager')],
        compute='_compute_assessor_role',
        store=True,
    )
    review_period = fields.Selection([('monthly', 'Monthly'), ('term', 'Term'), ('custom', 'Custom')], default='custom')
    term_id = fields.Many2one('sfk.term', string='Term')
    period_start = fields.Date()
    period_end = fields.Date()
    summary = fields.Text()
    line_ids = fields.One2many('sfk.quality.assessment.line', 'assessment_id', string='Answers')
    submitted_on = fields.Datetime(readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    @api.depends('assessor_id')
    def _compute_assessor_role(self):
        for rec in self:
            user = rec.assessor_id
            role = False
            if user.has_group('sfk_operation.group_sfk_coach_manager'):
                role = 'coach_manager'
            elif user.has_group('sfk_operation.group_sfk_supervisor'):
                role = 'supervisor'
            elif user.has_group('sfk_operation.group_sfk_instructor'):
                role = 'instructor'
            rec.assessor_role = role

    @api.onchange('request_id')
    def _onchange_request_id(self):
        for rec in self:
            if not rec.request_id:
                continue
            rec.target_type = rec.request_id.request_type
            rec.session_id = rec.request_id.session_id
            rec.program_id = rec.request_id.program_id
            rec.review_period = rec.request_id.review_period
            rec.term_id = rec.request_id.term_id
            rec.period_start = rec.request_id.period_start
            rec.period_end = rec.request_id.period_end

    @api.onchange('target_type', 'session_id')
    def _onchange_target(self):
        for rec in self:
            if rec.target_type == 'session' and rec.session_id:
                rec.program_id = rec.session_id.program_id

    @api.onchange('template_id')
    def _onchange_template_id(self):
        for rec in self:
            lines = []
            for q in rec.template_id.question_ids:
                lines.append((0, 0, {'question_id': q.id}))
            rec.line_ids = lines

    @api.constrains('target_type', 'session_id', 'program_id', 'template_id')
    def _check_target_and_template(self):
        for rec in self:
            if rec.target_type == 'session' and not rec.session_id:
                raise exceptions.ValidationError('Session is required for session-level assessment.')
            if rec.target_type == 'program' and not rec.program_id:
                raise exceptions.ValidationError('Program is required for program-level assessment.')
            if rec.template_id and rec.template_id.target_type != rec.target_type:
                raise exceptions.ValidationError('Template target type must match assessment target type.')

    def _check_submit_permissions(self):
        self.ensure_one()
        if not self.assessor_role:
            raise exceptions.AccessError('You do not have a quality assessment role.')
        if self.template_role_type != self.assessor_role:
            raise exceptions.AccessError('Your role does not match the selected assessment template.')

        if self.template_role_type == 'instructor' and self.target_type == 'session':
            session = self.session_id
            user = self.env.user
            is_assigned = (
                session.lead_instructor_id.user_id == user or
                session.assistant_instructor_id.user_id == user
            )
            if not is_assigned:
                raise exceptions.AccessError('Instructor assessment is allowed only for your assigned sessions.')

        if self.template_role_type in ('supervisor', 'coach_manager') and self.target_type == 'program':
            program = self.program_id
            user = self.env.user
            if self.template_role_type == 'supervisor' and program.supervisor_id != user:
                raise exceptions.AccessError('Supervisor can assess only assigned programs.')
            if self.template_role_type == 'coach_manager' and program.manager_id != user and not user.has_group('sfk_operation.group_sfk_manager'):
                raise exceptions.AccessError('Coach Manager can assess only assigned programs.')

    def action_submit(self):
        for rec in self:
            rec._check_submit_permissions()
            for line in rec.line_ids:
                line._check_required_answer()
            rec.write({'state': 'submitted', 'submitted_on': fields.Datetime.now()})

    def action_approve(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_manager'):
            raise exceptions.AccessError('Only Operation Managers can approve quality assessments.')
        self.write({'state': 'approved'})

    def action_reject(self):
        if not self.env.user.has_group('sfk_operation.group_sfk_manager'):
            raise exceptions.AccessError('Only Operation Managers can reject quality assessments.')
        self.write({'state': 'rejected'})


class SfkQualityAssessmentLine(models.Model):
    _name = "sfk.quality.assessment.line"
    _description = "Quality Assessment Answer"
    _order = "id"

    assessment_id = fields.Many2one('sfk.quality.assessment', required=True, ondelete='cascade')
    question_id = fields.Many2one('sfk.quality.template.question', required=True)
    answer_type = fields.Selection(related='question_id.answer_type', store=True)
    max_score = fields.Float(related='question_id.max_score', store=True)
    options = fields.Char(related='question_id.options')

    text_answer = fields.Text()
    score_answer = fields.Float()
    selection_answer = fields.Char()
    notes = fields.Char()

    def _check_required_answer(self):
        for rec in self:
            if not rec.question_id.required:
                continue
            if rec.answer_type == 'text' and not rec.text_answer:
                raise exceptions.ValidationError('Please answer all required text questions.')
            if rec.answer_type == 'score' and rec.score_answer is False:
                raise exceptions.ValidationError('Please answer all required score questions.')
            if rec.answer_type == 'selection' and not rec.selection_answer:
                raise exceptions.ValidationError('Please answer all required selection questions.')
            if rec.answer_type == 'score' and rec.score_answer > rec.max_score:
                raise exceptions.ValidationError('Score cannot exceed the question max score.')
