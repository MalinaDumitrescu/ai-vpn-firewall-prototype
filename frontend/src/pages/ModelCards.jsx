import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import WarningBox from '../components/WarningBox.jsx';
import FeatureFormulaTable from '../components/FeatureFormulaTable.jsx';

const ACTIVE_MODEL = 'unified_relative_shape_v2__lgbm';

const BADGE_ACCENT = {
  'CURRENT MODEL':                'ok',
  'EXECUTABLE':                   'ok',
  'UNIFIED FEATURE CONTRACT V2':  'info',
  'SIMULATION ONLY':              'warn',
  'NOT PRODUCTION READY':         'bad',
  'LEGACY MIXED-FEATURE BASELINE':'bad',
  'COMPARISON ONLY':              'neutral',
  'NOT CURRENT MODEL':            'bad',
  'DOMAIN AUC = 1.0':             'bad',
  'LEGACY':                       'neutral',
  'NEGATIVE CONTROL':             'bad',
  'REPORT ONLY':                  'neutral',
  'NOT DEPLOYABLE':               'bad',
  'SUPERSEDED':                   'neutral',
};

function badge(label) {
  const accent = BADGE_ACCENT[label] || 'neutral';
  return (
    <span key={label} className={`badge ${accent}`} style={{ fontSize: 11 }}>
      {label}
    </span>
  );
}

function n(v, d = 4) {
  if (v === null || v === undefined) return '—';
  if (typeof v !== 'number') return String(v);
  if (Number.isInteger(v)) return v.toString();
  return v.toFixed(d);
}

function MetricsKv({ metrics }) {
  if (!metrics) return null;
  const rows = [
    ['test_auc',       'Test AUC'],
    ['lodo_min_auc',   'LODO-min AUC'],
    ['lodo_iscx_auc',  'LODO ISCX AUC'],
    ['lodo_vnat_auc',  'LODO VNAT AUC'],
    ['lodo_mean_auc',  'LODO mean AUC'],
    ['domain_auc',     'Domain AUC'],
    ['test_recall',    'Recall'],
    ['test_fpr',       'FPR'],
    ['test_ece',       'ECE'],
    ['deployment_score','Deploy Score'],
  ].filter(([k]) => metrics[k] !== undefined && metrics[k] !== null);

  if (rows.length === 0 && metrics.note) {
    return <div className="dim" style={{ fontSize: 12, marginTop: 6 }}>{metrics.note}</div>;
  }

  return (
    <div className="kv" style={{ marginTop: 8 }}>
      {rows.map(([k, label]) => (
        <React.Fragment key={k}>
          <div className="k">{label}</div>
          <div className="v mono">{n(metrics[k])}</div>
        </React.Fragment>
      ))}
    </div>
  );
}

function RichModelCard({ modelId, card, featuresData }) {
  const [expanded, setExpanded] = useState(false);
  const isActive = modelId === ACTIVE_MODEL;
  const cardFeatures = featuresData?.models?.[modelId]?.features ?? {};

  return (
    <div
      className={`card${isActive ? ' card--active-model' : ''}`}
      style={isActive ? { borderColor: 'var(--ok)', boxShadow: '0 0 0 1px var(--ok)' } : {}}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 15 }}>{card.title}</h2>
          <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>{card.subtitle}</div>
        </div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {(card.badges ?? []).map(badge)}
        </div>
      </div>

      {/* Short explanation */}
      {card.short_explanation && (
        <p style={{ fontSize: 13, lineHeight: 1.6, marginTop: 10, marginBottom: 0, color: 'var(--text-dim)' }}>
          {card.short_explanation}
        </p>
      )}

      {/* Why selected / why not selected */}
      {card.why_selected && (
        <div style={{ marginTop: 12 }}>
          <div className="dim" style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 5 }}>
            Why selected
          </div>
          <ul className="clean" style={{ fontSize: 12, margin: 0, paddingLeft: 0 }}>
            {card.why_selected.map((r, i) => (
              <li key={i} style={{ padding: '2px 0', color: 'var(--text-dim)', display: 'flex', gap: 6 }}>
                <span style={{ color: 'var(--ok)', flexShrink: 0 }}>✓</span>{r}
              </li>
            ))}
          </ul>
        </div>
      )}
      {card.why_not_selected && (
        <div style={{ marginTop: 12 }}>
          <div className="dim" style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 5 }}>
            Why not selected
          </div>
          <ul className="clean" style={{ fontSize: 12, margin: 0, paddingLeft: 0 }}>
            {card.why_not_selected.map((r, i) => (
              <li key={i} style={{ padding: '2px 0', color: 'var(--text-dim)', display: 'flex', gap: 6 }}>
                <span style={{ color: 'var(--bad)', flexShrink: 0 }}>✗</span>{r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Toggle for metrics / calibration / caveats / features */}
      <button
        className="secondary"
        style={{ fontSize: 12, padding: '5px 12px', marginTop: 12 }}
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? '▲ Less detail' : '▼ Metrics, calibration & caveats'}
      </button>

      {expanded && (
        <>
          {/* Metrics */}
          {card.metrics && (
            <div style={{ marginTop: 12 }}>
              <div className="dim" style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 4 }}>Metrics</div>
              <MetricsKv metrics={card.metrics} />
            </div>
          )}

          {/* Thresholds */}
          {card.thresholds && (
            <div style={{ marginTop: 12 }}>
              <div className="dim" style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 4 }}>Thresholds</div>
              <div className="kv">
                {card.thresholds.review !== undefined && (
                  <><div className="k">review</div><div className="v mono">{card.thresholds.review}</div></>
                )}
                {card.thresholds.block !== undefined && (
                  <><div className="k">block</div><div className="v mono">{card.thresholds.block}</div></>
                )}
                {card.thresholds.policy && (
                  <><div className="k">policy</div><div className="v mono">{card.thresholds.policy}</div></>
                )}
              </div>
            </div>
          )}

          {/* Calibration */}
          {card.calibration && (
            <div style={{ marginTop: 12 }}>
              <div className="dim" style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 4 }}>Calibration</div>
              <div className="kv">
                <div className="k">method</div>
                <div className="v mono">{card.calibration.method}</div>
                <div className="k">ECE</div>
                <div className="v mono">{card.calibration.ece}</div>
              </div>
              {card.calibration.warning && (
                <div className="warning-box warn" style={{ marginTop: 8, marginBottom: 0 }}>
                  <span className="icon">⚠</span>
                  <div style={{ fontSize: 12 }}>{card.calibration.warning}</div>
                </div>
              )}
            </div>
          )}

          {/* Caveats */}
          {card.caveats && card.caveats.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="dim" style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 5 }}>Caveats</div>
              <ul className="clean" style={{ fontSize: 12, margin: 0, paddingLeft: 0 }}>
                {card.caveats.map((c, i) => (
                  <li key={i} style={{ padding: '2px 0', color: 'var(--text-dim)', display: 'flex', gap: 6 }}>
                    <span style={{ color: 'var(--warn)', flexShrink: 0 }}>⚠</span>{c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Live extractor status */}
          <div style={{ marginTop: 10, display: 'flex', gap: 12, fontSize: 12, color: 'var(--text-dim)' }}>
            <span>
              Live extractor:{' '}
              {card.live_extractor_compatible
                ? <span style={{ color: 'var(--ok)' }}>✓ compatible</span>
                : <span style={{ color: 'var(--bad)' }}>✗ not compatible</span>}
            </span>
            <span>PCAP status: <span className="mono">{card.live_pcap_status ?? '—'}</span></span>
          </div>

          {/* Feature formulas */}
          {Object.keys(cardFeatures).length > 0 && (
            <FeatureFormulaTable
              featuresObj={cardFeatures}
              selectedOnly={isActive}
            />
          )}
        </>
      )}
    </div>
  );
}

export default function ModelCards() {
  const [cards, setCards]           = useState(null);
  const [features, setFeatures]     = useState(null);
  const [pageContent, setPageContent] = useState(null);
  const [error, setError]           = useState(null);
  const [loading, setLoading]       = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [c, f, pc] = await Promise.all([
          api.modelDetailsCards(),
          api.modelDetailsFeatures(),
          api.modelDetailsFrontendContent(),
        ]);
        setCards(c);
        setFeatures(f);
        setPageContent(pc);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="loading-line"><span className="spinner" />Loading model cards…</div>;
  if (error)   return <div className="error-box">Failed to load model cards: {error}</div>;

  const cardsMap  = cards?.cards  ?? {};
  const sections  = pageContent?.pages?.ModelsPage?.sections ?? [];
  const badgesMap = pageContent?.pages?.ModelsPage?.card_badges ?? {};

  // Merge in additional badges from page content
  const mergedCards = Object.fromEntries(
    Object.entries(cardsMap).map(([id, card]) => [
      id,
      {
        ...card,
        badges: [...new Set([...(badgesMap[id] ?? []), ...(card.badges ?? [])])],
      },
    ]),
  );

  return (
    <div>
      <WarningBox tone="info">
        <strong>
          <span className="mono">unified_relative_shape_v2__lgbm</span> — CURRENT MODEL · EXECUTABLE · UNIFIED FEATURE CONTRACT V2
        </strong>{' '}
        Simulation-only. Not production-ready.{' '}
        <span className="mono">full_canonical__lgbm</span> — LEGACY MIXED-FEATURE BASELINE / comparison-only — not the recommended model.
      </WarningBox>

      {sections.length > 0 ? (
        sections.map((sec) => {
          const sectionCards = (sec.models ?? [])
            .map((id) => [id, mergedCards[id]])
            .filter(([, c]) => !!c);
          if (sectionCards.length === 0) return null;
          return (
            <div key={sec.section_id} className="section">
              <div className="page-header" style={{ marginBottom: 10 }}>
                <h1 style={{ fontSize: 16 }}>{sec.title}</h1>
                {sec.note && <div className="subtitle">{sec.note}</div>}
              </div>
              <div className="grid cols-2">
                {sectionCards.map(([id, card]) => (
                  <RichModelCard key={id} modelId={id} card={card} featuresData={features} />
                ))}
              </div>
            </div>
          );
        })
      ) : (
        // Fallback: flat list of all cards
        <div className="grid cols-2">
          {Object.entries(mergedCards).map(([id, card]) => (
            <RichModelCard key={id} modelId={id} card={card} featuresData={features} />
          ))}
        </div>
      )}
    </div>
  );
}

