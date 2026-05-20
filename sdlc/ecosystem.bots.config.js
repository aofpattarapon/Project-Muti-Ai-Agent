const PY  = '/home/off_poff_p/projects/multi-ai-agent/sdlc/venv/bin/python';
const CWD = '/home/off_poff_p/projects/multi-ai-agent/sdlc';
const ENV = '/home/off_poff_p/projects/multi-ai-agent/sdlc/.env';

const base = (name, args) => ({
  name, script: PY, args, cwd: CWD, interpreter: 'none', env_file: ENV,
  restart_delay: 5000, max_restarts: 10, min_uptime: '10s',
});

module.exports = {
  apps: [
    base('sdlc-ceo',    '-m agents.ceo.agent'),
    base('sdlc-pm',     '-m agents.pm.agent'),
    base('sdlc-ba',     '-m agents.ba.agent'),
    base('sdlc-sa',     '-m agents.sa.agent'),
    base('sdlc-uxui',   '-m agents.uxui.agent'),
    base('sdlc-dev',    '-m agents.dev.combined_agent'),
    base('sdlc-qa',     '-m agents.qa.agent'),
    base('sdlc-devops', '-m agents.devops.agent'),
    base('sdlc-cron',   'agents/hermes_cron.py'),   // Hermes Cron — background jobs
    base('sdlc-quota-recovery', 'agents/recovery_worker.py'),
  ]
}
