export const STATUS_LABELS = {
  queued: 'Starting',
  drafting_brief: 'Writing brief',
  researching: 'Researching',
  specialists_working: 'Specialists working',
  reviewing: 'Reviewing',
  awaiting_approval: 'Needs your approval',
  writing_plan: 'Writing final plan',
  done: 'Done',
  failed: 'Failed',
}

export const STEPS = [
  { label: 'Brief', statuses: ['queued', 'drafting_brief'] },
  { label: 'Research', statuses: ['researching'] },
  { label: 'Specialists', statuses: ['specialists_working'] },
  { label: 'Review', statuses: ['reviewing'] },
  { label: 'Your approval', statuses: ['awaiting_approval'] },
  { label: 'Final plan', statuses: ['writing_plan', 'done'] },
]

export const BUSY = new Set(['queued', 'drafting_brief', 'researching', 'specialists_working', 'reviewing', 'writing_plan'])
