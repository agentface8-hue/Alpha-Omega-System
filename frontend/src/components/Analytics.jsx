import { useState, useEffect } from 'react';
import { Activity, BarChart3, AlertTriangle, TrendingUp } from 'lucide-react';
import { C, StatCard, SectionCard, PageHeader, BarRow, Badge, EmptyState, LoadingSpinner } from './UIKit';

import { API_BASE } from '../utils/api';

const API = API_BASE;

const Analytics = () => {
  const [data,    setData]    = useState(null);
  const [risk,    setRisk]    = useState(null);
  const [source,  setSource]  = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [perfRes, riskRes, srcRes] = await Promise.all([
          fetch(`${API}/api/analytics/performance`),
          fetch(`${API}/api/portfolio/risk`),
          fetch(`${API}/api/data/source`),
        ]);
        if (perfRes.ok) setData(await perfRes.json());
        if (riskRes.ok) setRisk(await riskRes.json());
        if (srcRes.ok)  setSource(await srcRes.json());
      } catch(e) { console.error(e); }
      setLoading(false);
    };
    load();
  }, []);

  const riskColor = risk?.risk_level === 'HIGH' ? C.red : risk?.risk_level === 'MEDIUM' ? C.yellow : C.green;

  return (
    <div style={{ padding: '28px 28px', maxWidth: 1060, margin: '0 auto' }}>

      <PageHeader
        icon={<Activity size={18} />}
        title="ANALYTICS"
        subtitle="LEARNING LOOP · RISK · PERFORMANCE"
        right={source && (
          <Badge
            label={source.label}
            color={source.realtime ? C.green : C.yellow}
            size="lg"
          />
        )}
      />

      {loading && <LoadingSpinner text="Loading analytics..." />}

      {!loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Portfolio Risk */}
          {risk && (
            <SectionCard
              title="PORTFOLIO RISK"
              subtitle={`${risk.signals || 0} open signals · worst-case ${risk.worst_case_loss_pct || 0}% drawdown`}
              accent={riskColor}
              action={<Badge label={risk.risk_level} color={riskColor} size="lg" />}
            >
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: risk.warnings?.length ? 16 : 0 }}>
                <StatCard label="Open Signals"  value={risk.signals}     color={C.text}  minWidth={110} />
                <StatCard label="Worst Case"    value={`${risk.worst_case_loss_pct}%`}
                  color={risk.worst_case_loss_pct < -2 ? C.red : C.yellow}
                  sub="if all SLs hit" minWidth={120} />
                {Object.entries(risk.sector_exposure || {}).map(([sec, cnt]) => (
                  <StatCard key={sec} label={sec} value={cnt}
                    color={cnt >= 3 ? C.red : cnt === 2 ? C.yellow : C.green}
                    sub="signals" minWidth={100} />
                ))}
              </div>

              {risk.warnings?.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {risk.warnings.map((w, i) => (
                    <div key={i} style={{
                      background: '#1a0a0a', border: `1px solid ${C.red}25`,
                      borderRadius: 6, padding: '8px 14px',
                      color: '#ff8899', fontSize: 10, fontFamily: 'sans-serif',
                      display: 'flex', alignItems: 'center', gap: 8,
                    }}>
                      <AlertTriangle size={11} color={C.red} />
                      {w}
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          )}

          {/* Overall Performance */}
          {data?.total > 0 ? (
            <>
              <SectionCard title="PERFORMANCE" subtitle={`${data.total} closed trades`} accent={C.blue}>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  <StatCard label="Total Trades"   value={data.total}              color={C.text}   minWidth={110} />
                  <StatCard label="Win Rate"        value={`${data.win_rate}%`}
                    color={data.win_rate >= 55 ? C.green : data.win_rate >= 45 ? C.yellow : C.red}
                    accent={data.win_rate >= 55 ? C.green : data.win_rate >= 45 ? C.yellow : C.red}
                    minWidth={110} />
                  <StatCard label="Profit Factor"  value={data.profit_factor}
                    color={data.profit_factor >= 1.5 ? C.green : data.profit_factor >= 1 ? C.yellow : C.red}
                    sub="> 1.5 = strong" minWidth={120} />
                  <StatCard label="Avg Win"         value={`+${data.avg_win_pct}%`}  color={C.green}  minWidth={110} />
                  <StatCard label="Avg Loss"         value={`${data.avg_loss_pct}%`}  color={C.red}    minWidth={110} />
                  <StatCard label="TP1 Hit Rate"     value={`${data.tp1_hit_rate}%`}  color={C.blue}   minWidth={110} />
                  <StatCard label="Stopped Out"      value={`${data.stopped_out_rate}%`} color={C.red} minWidth={110} />
                  <StatCard label="Avg MFE"          value={`+${data.avg_mfe_pct}%`}  color={C.green}  sub="best unrealized" minWidth={110} />
                  <StatCard label="Avg MAE"          value={`${data.avg_mae_pct}%`}   color={C.red}    sub="worst drawdown"  minWidth={110} />
                </div>
              </SectionCard>

              {Object.keys(data.conviction_breakdown || {}).length > 0 && (
                <SectionCard title="WIN RATE BY CONVICTION" subtitle="Does higher conviction actually win more?" accent={C.purple}>
                  {Object.entries(data.conviction_breakdown).map(([bucket, d]) => (
                    <BarRow key={bucket}
                      label={`${bucket}% conviction`}
                      pct={d.win_rate}
                      count={d.trades}
                      color={d.win_rate >= 60 ? C.green : d.win_rate >= 50 ? C.yellow : C.red}
                    />
                  ))}
                </SectionCard>
              )}

              {Object.keys(data.regime_breakdown || {}).length > 0 && (
                <SectionCard title="WIN RATE BY REGIME" subtitle="When does the system perform best?" accent={C.yellow}>
                  {Object.entries(data.regime_breakdown).map(([reg, d]) => (
                    <BarRow key={reg}
                      label={reg || 'Unknown'}
                      pct={d.win_rate}
                      count={d.trades}
                      color={d.win_rate >= 60 ? C.green : d.win_rate >= 50 ? C.yellow : C.red}
                    />
                  ))}
                </SectionCard>
              )}
            </>
          ) : (
            <SectionCard title="PERFORMANCE" accent={C.blue}>
              <EmptyState
                icon={<BarChart3 size={36} />}
                title="No closed trades yet"
                subtitle="Run Auto-Pilot to generate signals. Analytics appear once trades close."
              />
            </SectionCard>
          )}

        </div>
      )}
    </div>
  );
};

export default Analytics;
