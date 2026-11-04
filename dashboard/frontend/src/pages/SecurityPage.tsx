import { useEffect, useState } from 'react';

interface SecurityCheck {
  name: string;
  status?: 'pass' | 'fail' | 'warn' | 'info';
  message?: string;
  // backend alternate shape
  check?: string;
  pass?: boolean;
  details?: string;
}

interface SecurityStatus {
  overall?: string;
  checks?: SecurityCheck[];
  checked_at?: string;
}

// Normalize both {name, status, message} and {check, pass, details} shapes.
function normalizeCheck(c: SecurityCheck): { name: string; status: 'pass' | 'fail' | 'warn' | 'info'; message?: string } {
  let status: 'pass' | 'fail' | 'warn' | 'info';
  if (typeof c.status === 'string') {
    const s = c.status.toLowerCase();
    status = (s === 'pass' || s === 'fail' || s === 'warn' || s === 'info') ? s as 'pass' | 'fail' | 'warn' | 'info' : (s.includes('pass') || s.includes('ok') ? 'pass' : 'info');
  } else if (typeof c.pass === 'boolean') {
    status = c.pass ? 'pass' : 'fail';
  } else {
    status = 'info';
  }
  return {
    name: c.name || c.check || 'Check',
    status,
    message: c.message || c.details,
  };
}

export default function SecurityPage() {
  const [status, setStatus] = useState<SecurityStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchSecurity = async () => {
      try {
        const resp = await fetch('/api/v1/security/status', { cache: 'no-store' });
        if (!resp.ok) throw new Error('unavailable');
        const data = await resp.json();
        setStatus(data);
        setError(false);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    };
    fetchSecurity();
    const timer = setInterval(fetchSecurity, 30_000);
    return () => clearInterval(timer);
  }, []);

  const overallColor = (s: string) => {
    if (s === 'pass' || s === 'secure') return '#02a0a0';
    if (s === 'warn' || s === 'warning') return '#ffbd65';
    if (s === 'fail' || s === 'critical') return '#ff4444';
    return '#8fa8a5';
  };

  const checkColors: Record<string, string> = {
    pass: 'text-[#02a0a0] bg-[#02a0a0]/10 border-[#02a0a0]/20',
    fail: 'text-[#ff4444] bg-[#ff4444]/10 border-[#ff4444]/20',
    warn: 'text-[#ffbd65] bg-[#ffbd65]/10 border-[#ffbd65]/20',
    info: 'text-[#8fa8a5] bg-[#8fa8a5]/10 border-[#8fa8a5]/20',
  };

  const checkIcons: Record<string, string> = {
    pass: '●',
    fail: '●',
    warn: '●',
    info: '○',
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-lg text-[#d9ece9] tracking-wider uppercase">Security</h1>
        <p className="text-[#5d7573] text-[11px] mt-0.5">
          {status?.checked_at ? `Security checks · updated ${new Date(status.checked_at).toLocaleTimeString()}` : 'System security audit results'}
          {error ? ' · refresh unavailable' : ''}
        </p>
      </div>

      {loading ? (
        <div className="text-[#8fa8a5] text-sm">Running security checks...</div>
      ) : !status || !Array.isArray(status.checks) || status.checks.length === 0 ? (
        <div className="bg-[#10262b] border border-[#1e383b] rounded-2xl p-6 text-center">
          <div className="text-[#5d7573] text-sm">Security endpoint unavailable</div>
          <p className="text-[#5d7573] text-[10px] mt-1">
            Ensure /api/v1/security/status is implemented
          </p>
        </div>
      ) : (
        <div>
          {/* Overall status */}
          {status.overall && (
            <div className="bg-[#10262b] border border-[#1e383b] rounded-2xl p-4 mb-4 flex items-center gap-3">
              <span
                className="text-sm font-bold uppercase tracking-wider"
                style={{ color: overallColor(status.overall) }}
              >
                {status.overall}
              </span>
              <span className="text-[#5d7573] text-[10px]">Overall Security Status</span>
            </div>
          )}

          {/* Checks list */}
          <div className="space-y-2">
            {status.checks.map((raw, idx) => {
              const check = normalizeCheck(raw);
              return (
              <div
                key={idx}
                className="bg-[#10262b] border border-[#1e383b] rounded-2xl px-4 py-3 flex items-start gap-3 hover:border-[#02a0a0]/30 transition-colors"
              >
                <span
                  className={`text-[10px] px-2 py-0.5 rounded border ${checkColors[check.status] || checkColors.info}`}
                >
                  {checkIcons[check.status] || '○'} {check.status.toUpperCase()}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-[#d9ece9] text-sm">{check.name}</div>
                  {check.message && (
                    <div className="text-[#5d7573] text-[11px] mt-0.5">{check.message}</div>
                  )}
                </div>
              </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}