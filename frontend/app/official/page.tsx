"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import VacancyMap from "@/components/official/VacancyMap";
import { api } from "@/lib/api";
import { METRIC_THRESHOLDS, VACANCY_COLORS, metricValue, vacancyColor, type RegionScope, type RegionStatsResponse, type VacancyMetric } from "@/lib/regionTypes";
import "./official.css";

const number = (value: number) => value.toLocaleString("ko-KR");

export default function OfficialPage() {
  const [data, setData] = useState<RegionStatsResponse | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [scope, setScope] = useState<RegionScope>("district");
  const [metric, setMetric] = useState<VacancyMetric>("count");
  const [selectedId, setSelectedId] = useState("jeonju");
  const onSelect = useCallback((id: string) => setSelectedId(id), []);

  useEffect(() => {
    let cancelled = false;
    api.getRegionStats().then((result) => {
      if (!cancelled) setData(result);
    }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [attempt]);

  const regions = useMemo(() => data?.regions.filter((region) => region.scope === scope) ?? [], [data, scope]);
  const ranked = useMemo(() => [...regions].sort((a, b) => metricValue(b, metric) - metricValue(a, metric)), [regions, metric]);
  const selected = regions.find((region) => region.id === selectedId) ?? regions[0];
  const totals = regions.reduce((sum, r) => ({
    units: sum.units + r.total_units,
    vacant: sum.vacant + r.vacant_units,
    previous: sum.previous + (r.monthly_vacant_units.at(-2) ?? r.vacant_units),
    duration: sum.duration + r.avg_vacancy_period_months * r.vacant_units,
  }), { units: 0, vacant: 0, previous: 0, duration: 0 });
  const rate = totals.units ? totals.vacant / totals.units * 100 : 0;
  const change = totals.units ? (totals.vacant - totals.previous) / totals.units * 100 : 0;
  const highestRate = [...regions].sort((a, b) => b.vacancy_rate - a.vacancy_rate)[0];
  const scopeName = scope === "district" ? "전북 전체" : "전주 시범 상권";
  const trendMax = Math.max(40, ...selected?.vacancy_trend_6m ?? []);

  function changeScope(next: RegionScope) {
    setScope(next);
    setSelectedId(next === "district" ? "jeonju" : "gyeongwon");
  }

  return (
    <div className="official-shell">
      <header className="official-header">
        <Link href="/" className="official-brand" aria-label="채움 홈"><span className="brand-symbol">ㅊ</span>채움<span className="brand-divider" />지자체 콘솔</Link>
        <Link href="/" className="official-home">역할 변경 ↗</Link>
      </header>
      <main className="official-main">
        <div className="official-heading">
          <div><p className="official-eyebrow">지역의 빈 공간, 새로운 가능성</p><h1>공실 현황 대시보드</h1><p className="official-subtitle">전북의 공실 분포를 살펴보고, 지역별 현황을 비교하세요.</p></div>
          <div className="reference-badge"><span className="status-dot" />{data?.data_reference_month.replace("-", ". ") ?? "—"} 기준{data?.is_mock && <span className="mock-badge">목업 데이터</span>}</div>
        </div>

        {error ? <section className="official-state" role="alert"><h2>공실 데이터를 불러오지 못했습니다</h2><p>백엔드 서버 연결을 확인한 후 다시 시도해 주세요.</p><button className="primary-button" onClick={() => { setError(false); setAttempt((value) => value + 1); }}>다시 시도</button></section>
        : !data ? <section className="official-state" role="status"><span className="loading-dot" /><h2>전북 지역별 현황을 불러오고 있습니다</h2></section>
        : !regions.length || !selected ? <section className="official-state"><h2>표시할 지역 데이터가 없습니다</h2><button className="primary-button" onClick={() => changeScope("district")}>전북 전체 보기</button></section>
        : <>
          <div className="dashboard-toolbar">
            <div className="segmented" role="group" aria-label="조회 권역">
              <button aria-pressed={scope === "district"} onClick={() => changeScope("district")}>전북 전체 <span>14개 시·군</span></button>
              <button aria-pressed={scope === "neighborhood"} onClick={() => changeScope("neighborhood")}>전주 시범 상권 <span>5개</span></button>
            </div>
            <span className="toolbar-note">기준월 말 집계 · 상가 단위</span>
          </div>

          <section className="stat-grid" aria-label={scopeName + " 주요 지표"}>
            <article className="stat-card"><p>전체 공실 수 <span>01</span></p><strong>{number(totals.vacant)}<small>개</small></strong><div>집계 대상 상가 {number(totals.units)}개</div></article>
            <article className="stat-card"><p>전체 공실률 <span>02</span></p><strong>{rate.toFixed(1)}<small>%</small></strong><div><span className={change > 0 ? "change-up" : "change-down"}>{change > 0 ? "↑" : change < 0 ? "↓" : "—"} {Math.abs(change).toFixed(2)}%p</span> 전월 대비</div></article>
            <article className="stat-card"><p>공실률이 가장 높은 지역 <span>03</span></p><strong className="region-stat">{highestRate.region_name}<small>{highestRate.vacancy_rate.toFixed(1)}%</small></strong><div>공실 {number(highestRate.vacant_units)}개 · 지역 상세에서 확인</div></article>
            <article className="stat-card"><p>평균 공실 기간 <span>04</span></p><strong>{(totals.vacant ? totals.duration / totals.vacant : 0).toFixed(1)}<small>개월</small></strong><div>현재 공실 수를 기준으로 가중 평균</div></article>
          </section>

          <section className="map-detail-grid">
            <article className="official-panel map-panel">
              <div className="panel-heading"><div><p className="section-label">VACANCY MAP</p><h2>{scopeName} 공실 분포</h2></div><div className="metric-toggle" role="group" aria-label="지도 표시 지표"><button aria-pressed={metric === "count"} onClick={() => setMetric("count")}>공실 수</button><button aria-pressed={metric === "rate"} onClick={() => setMetric("rate")}>공실률</button></div></div>
              <VacancyMap regions={regions} selectedId={selected.id} metric={metric} onSelect={onSelect} />
              <div className="map-legend"><strong>{metric === "count" ? "공실 수 (개)" : "공실률 (%)"}</strong><div>{VACANCY_COLORS.map((color, i) => {
                const thresholds = METRIC_THRESHOLDS[metric];
                const label = i === 0 ? thresholds[0] + " 미만" : i === 4 ? thresholds[3] + " 이상" : thresholds[i - 1] + "–" + thresholds[i] + " 미만";
                return <span key={color}><i style={{ background: color }} />{label}</span>;
              })}</div></div>
              <p className="map-caption">색이 진하고 원이 클수록 {metric === "count" ? "공실 수가 많습니다" : "공실률이 높습니다"}. 원은 지역 대표 지점이며 행정구역 경계·실제 공실 위치가 아닙니다.</p>
            </article>

            <aside className="official-panel detail-panel" aria-label="선택 지역 상세" aria-live="polite">
              <p className="section-label">REGION INSIGHT</p>
              <div className="detail-title"><h2>{selected.region_name}</h2><span>선택 지역</span></div>
              <p className="detail-context">{scope === "district" ? "전북특별자치도 · 시·군 집계" : "전주시 · 시범 상권 집계"}</p>
              <div className="detail-rate"><strong>{selected.vacancy_rate.toFixed(1)}<small>%</small></strong><span>공실률</span></div>
              <div className="occupancy-track"><span style={{ width: selected.vacancy_rate + "%", background: vacancyColor(selected.vacancy_rate, "rate") }} /></div>
              <div className="detail-pair"><span>공실 <b>{number(selected.vacant_units)}개</b></span><span>전체 상가 <b>{number(selected.total_units)}개</b></span></div>
              <div className="detail-facts"><div><span>평균 공실 기간</span><strong>{selected.avg_vacancy_period_months}개월</strong></div><div><span>추천 업종 {data.is_mock && "(시나리오)"}</span><strong>{selected.top_recommended_business}</strong></div></div>
              <div className="trend-heading"><h3>{data.months.length > 1 ? `최근 ${data.months.length}개월 공실률` : "공실률 (단일 기준월)"}</h3><span>{data.months.length > 1 ? `${data.months[0].slice(5)}–${data.months.at(-1)?.slice(5)}월` : `${data.months[0].replace("-", ". ")} 기준`}</span></div>
              <svg className="trend-chart" viewBox="0 0 280 110" role="img" aria-label={selected.region_name + " 월별 공실률: " + data.months.map((month, i) => month + " " + selected.vacancy_trend_6m[i] + "%").join(", ")}>
                {[0, trendMax / 2, trendMax].map((tick) => <g key={tick}><line x1="28" y1={85 - tick / trendMax * 80} x2="269" y2={85 - tick / trendMax * 80} stroke="#e8e2da" strokeDasharray="3 4" /><text x="0" y={89 - tick / trendMax * 80} fontSize="10" fill="#8a8078">{tick}%</text></g>)}
                <polyline fill="none" stroke="#b5502e" strokeWidth="2.5" strokeLinejoin="round" points={selected.vacancy_trend_6m.map((value, i) => (32 + i * 46) + "," + (85 - value / trendMax * 80)).join(" ")} />
                {selected.vacancy_trend_6m.map((value, i) => <g key={data.months[i]}><circle cx={32 + i * 46} cy={85 - value / trendMax * 80} r="3.5" fill="#b5502e"><title>{data.months[i]}: {value}%</title></circle><text x={32 + i * 46} y="105" textAnchor="middle" fontSize="10" fill="#8a8078">{Number(data.months[i].slice(5))}월</text></g>)}
              </svg>
              {selected.id === "jeonju" && <button className="detail-link" onClick={() => changeScope("neighborhood")}>전주 시범 상권 5개 살펴보기 <span>→</span></button>}
              {selected.building_id && <Link className="detail-link" href={"/diagnosis/" + selected.building_id}>연결된 데모 매물 진단 보기 <span>→</span></Link>}
              {!selected.building_id && selected.id !== "jeonju" && <p className="detail-note">이 지역은 집계 목업만 제공됩니다.</p>}
            </aside>
          </section>

          <section className="official-panel comparison-panel">
            <div className="panel-heading"><div><p className="section-label">REGIONAL COMPARISON</p><h2>지역별 {metric === "count" ? "공실 수" : "공실률"} 비교</h2></div><span className="comparison-hint">높은 순 · 지역을 선택하면 상세 정보가 바뀝니다</span></div>
            <div className="comparison-grid">{ranked.map((region, index) => <button className="comparison-row" key={region.id} aria-pressed={selected.id === region.id} onClick={() => onSelect(region.id)}>
              <span className="rank-number">{String(index + 1).padStart(2, "0")}</span><span className="comparison-name">{region.region_name}</span>
              <span className="bar-track"><span style={{ width: (metricValue(region, metric) / Math.max(1, metricValue(ranked[0], metric)) * 100) + "%", background: vacancyColor(metricValue(region, metric), metric) }} /></span>
              <strong>{metric === "count" ? number(region.vacant_units) + "개" : region.vacancy_rate.toFixed(1) + "%"}</strong>
            </button>)}</div>
          </section>
          <footer className="official-footnote"><strong>{data.is_mock ? "시연용 목업 데이터 안내" : "집계 안내"}</strong><p>{data.description}</p>{data.months.length === 1 && <p>과거 이력이 없는 기준월 단일 스냅샷이므로 월별 추이는 제공하지 않습니다.</p>}<p>전체 공실률 = 공실 수 합계 ÷ 전체 상가 수 합계 × 100 · 전주 시범 상권은 전북 전체 집계에 중복 합산하지 않습니다.</p></footer>
        </>}
      </main>
    </div>
  );
}
