const { useState, useEffect, useMemo, useRef } = React;

// ── API helpers ──────────────────────────────────────────────────────────────
const ROOT_EL   = document.getElementById('root');
const CSRF      = () => ROOT_EL.dataset.csrf || '';
const CAN_EDIT  = ROOT_EL.dataset.canEdit === 'true';

async function apiFetch(url, opts = {}) {
  const headers = { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF(), ...(opts.headers || {}) };
  const res = await fetch(url, { ...opts, headers });
  if (!res.ok) throw new Error(`${res.status}`);
  if (res.status === 204) return null;
  return res.json();
}

// ============ Area icon helper ============
function AreaIcon({ areaKey, size = 12, stroke = 2 }) {
  const area = window.AREAS[areaKey];
  if (!area) return null;
  const path = window.ICONS[area.iconKey];
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
         dangerouslySetInnerHTML={{ __html: path }} />
  );
}

// ============ Match scoring ============
function expandQuery(query) {
  if (!query.trim()) return [];
  const raw = query.toLowerCase()
    .split(/[,;]| y | con | e /i)
    .map(s => s.trim())
    .filter(Boolean);
  const out = [];
  for (const r of raw) {
    if (window.SYNONYMS[r]) out.push(window.SYNONYMS[r]);
    else out.push(r);
  }
  return out;
}

function scoreTherapist(t, queryTokens, selectedAreas) {
  if (!queryTokens.length && !selectedAreas.size) return { score: 0, hitTerms: new Set(), hitAreas: new Set() };
  const prepTerms = window.parsePrep(t.preparacion);
  const prepLower = prepTerms.map(x => x.toLowerCase());
  const hitTerms = new Set();
  const hitAreas = new Set();
  let score = 0;

  for (const tok of queryTokens) {
    const tokLow = tok.toLowerCase();
    let matched = false;
    prepLower.forEach((p, i) => {
      if (p === tokLow || p.includes(tokLow) || tokLow.includes(p)) {
        hitTerms.add(prepTerms[i]);
        hitAreas.add(window.termArea(prepTerms[i]));
        matched = true;
      }
    });
    if (!matched && t.formacion.toLowerCase().includes(tokLow)) {
      score += 0.5;
    }
    if (matched) score += 1;
  }

  for (const areaKey of selectedAreas) {
    let any = false;
    prepTerms.forEach((term) => {
      if (window.termArea(term) === areaKey) {
        hitTerms.add(term); hitAreas.add(areaKey); any = true;
      }
    });
    if (any) score += 1;
  }

  return { score, hitTerms, hitAreas };
}

// ============ Components ============

function Avatar({ name, size = "card" }) {
  const a = window.avatarFor(name);
  const dim = size === "lg" ? 80 : 54;
  return (
    <div className="avatar" style={{
      width: dim, height: dim,
      background: a.gradient,
      "--av-glow": `${a.c1}55`,
      "--av-c1": a.c1,
      borderRadius: size === "lg" ? 22 : 16,
      fontSize: size === "lg" ? 28 : 18,
    }}>
      <span className="ring"></span>
      {a.initials}
    </div>
  );
}

function TerapeutaCard({ t, score, hitTerms, hitAreas, query, onOpen, delay }) {
  const prepTerms = window.parsePrep(t.preparacion);
  const byArea = useMemo(() => {
    const m = {};
    for (const term of prepTerms) {
      const a = window.termArea(term);
      (m[a] ||= []).push(term);
    }
    return m;
  }, [t]);

  const accent = window.avatarFor(t.nombre).c1;
  const isPerfect = score > 0 && hitTerms.size >= 3;

  return (
    <article
      className="card entering"
      style={{ "--card-accent": accent, animationDelay: `${delay}ms` }}
      onClick={() => onOpen(t)}
    >
      <div className="card-top">
        <Avatar name={t.nombre} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 className="card-name">{t.nombre}</h3>
          <div className="card-meta">
            <span className={`titulo-badge ${t.titulo === "Maestría" ? "maestria" : "licenciatura"}`}>
              {t.titulo === "Maestría" ? "Mtra." : "Lic."}
            </span>
            <span className="cedula">{t.cedula}</span>
          </div>
        </div>
        {score > 0 && (
          <div className={`match-badge ${isPerfect ? "perfect" : ""}`}>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2l2.39 7.36H22l-6.18 4.49L18.21 22 12 17.27 5.79 22l2.39-8.15L2 9.36h7.61z" />
            </svg>
            {hitTerms.size} match{hitTerms.size === 1 ? "" : "es"}
          </div>
        )}
      </div>

      <div className="area-chips">
        {Object.entries(byArea).map(([areaKey, terms]) => {
          const area = window.AREAS[areaKey];
          const isHit = hitAreas?.has(areaKey);
          return (
            <span
              key={areaKey}
              className={`area-chip ${isHit ? "hit" : ""}`}
              style={{ "--chip-soft": area.soft, "--chip-color": area.color }}
            >
              <AreaIcon areaKey={areaKey} size={11} stroke={2.4} />
              {area.label} <span style={{ opacity: .7 }}>· {terms.length}</span>
            </span>
          );
        })}
      </div>

      <div className="terms-section">
        <div className="terms-label">Puede atender</div>
        <div className="terms-list">
          {prepTerms.map((term, i) => {
            const hit = hitTerms?.has(term);
            return (
              <React.Fragment key={i}>
                {hit ? <mark>{term}</mark> : term}
                {i < prepTerms.length - 1 && ", "}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      <div className="card-foot">
        <span className="foot-info">
          <b style={{ color: "var(--ink-2)" }}>{t.formacion.split(/[,;]/).length}</b> enfoques · {t.titulo}
        </span>
        <button className="assign-btn" onClick={(e) => { e.stopPropagation(); onOpen(t); }}>
          Ver perfil
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
        </button>
      </div>
    </article>
  );
}

function Drawer({ t, onClose, queryTokens, selectedAreas, onEdit, onDelete }) {
  useEffect(() => {
    if (!t) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [t, onClose]);

  if (!t) return null;
  const prepTerms = window.parsePrep(t.preparacion);
  const formaciones = t.formacion.split(/[,;]+/).map(x => x.trim()).filter(Boolean);
  const { hitTerms } = scoreTherapist(t, queryTokens, selectedAreas);

  const byArea = {};
  for (const term of prepTerms) {
    const a = window.termArea(term);
    (byArea[a] ||= []).push(term);
  }

  return (
    <>
      <div className={`drawer-backdrop ${t ? "open" : ""}`} onClick={onClose}></div>
      <aside className={`drawer ${t ? "open" : ""}`}>
        <div className="drawer-head">
          <button className="drawer-close" onClick={onClose} aria-label="Cerrar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
          <div className="drawer-hero">
            <Avatar name={t.nombre} size="lg" />
            <div>
              <h2 className="drawer-name">{t.nombre}</h2>
              <div className="drawer-meta">
                <span className={`titulo-badge ${t.titulo === "Maestría" ? "maestria" : "licenciatura"}`}>{t.titulo}</span>
                <span className="cedula">{t.cedula}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="drawer-body">
          <div className="field">
            <div className="field-label">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
              Áreas que atiende
            </div>
            <div>
              {Object.entries(byArea).map(([areaKey, terms]) => {
                const area = window.AREAS[areaKey];
                return (
                  <span key={areaKey} className="area-chip-lg" style={{ "--chip-soft": area.soft, "--chip-color": area.color }}>
                    <AreaIcon areaKey={areaKey} size={13} stroke={2.3} />
                    {area.label} · {terms.length}
                  </span>
                );
              })}
            </div>
          </div>

          <div className="field">
            <div className="field-label">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
              Lista completa de atención
            </div>
            <div className="field-value">
              {prepTerms.map((term, i) => {
                const hit = hitTerms?.has(term);
                return (
                  <React.Fragment key={i}>
                    {hit ? <mark>{term}</mark> : term}
                    {i < prepTerms.length - 1 && ", "}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          <div className="field">
            <div className="field-label">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
              Formación y enfoques
            </div>
            <div>
              {formaciones.map((f, i) => <span key={i} className="formacion-chip">{f}</span>)}
            </div>
          </div>

          <div className="cta-row">
            <button className="btn-primary" onClick={() => {
              const url = new URL('/', window.location.origin);
              url.searchParams.set('abrir_cita', '1');
              if (t.terapeuta_id) url.searchParams.set('terapeuta_id', t.terapeuta_id);
              window.location.href = url.href;
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/><path d="M12 14v4M10 16h4"/></svg>
              Agendar cita
            </button>
            {CAN_EDIT && (
              <>
                <button className="btn-secondary" onClick={() => onEdit(t)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  Editar
                </button>
                <button className="btn-icon-danger" onClick={() => {
                  if (confirm(`¿Eliminar a ${t.nombre} del catálogo?`)) { onDelete(t); onClose(); }
                }} title="Eliminar">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                </button>
              </>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}

// ============ Therapist Form Modal ============
const EMPTY = { nombre: "", titulo: "Licenciatura", cedula: "", preparacion: "", formacion: "", terapeuta_db_id: "" };
const ALL_TERMS = Object.values(window.AREAS).flatMap(a => a.terms);

function TherapistForm({ open, initial, onClose, onSave }) {
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [activeField, setActiveField] = useState(null);
  const [dbTerapeutas, setDbTerapeutas] = useState([]);
  const firstInputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setForm(initial
        ? { ...EMPTY, ...initial, terapeuta_db_id: initial.terapeuta_id ? String(initial.terapeuta_id) : "" }
        : EMPTY
      );
      setErrors({});
      setTimeout(() => firstInputRef.current?.focus(), 100);
      apiFetch('/api/terapeutas-activos/').then(setDbTerapeutas).catch(() => {});
    }
  }, [open, initial]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // useMemo MUST be before any early return (Rules of Hooks)
  const previewAreas = useMemo(() => {
    if (!form.preparacion) return [];
    const terms = window.parsePrep(form.preparacion);
    const seen = new Set();
    return terms.map(t => window.termArea(t)).filter(a => {
      if (seen.has(a)) return false; seen.add(a); return true;
    });
  }, [form.preparacion]);

  if (!open) return null;
  const isEdit = !!initial;

  const setField = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const addTermToField = (field, term) => {
    const cur = form[field].trim();
    const parts = cur ? cur.split(/,\s*/) : [];
    if (parts.includes(term)) return;
    parts.push(term);
    setField(field, parts.join(", "));
  };

  const removeTermFromField = (field, idx) => {
    const parts = form[field].split(/,\s*/);
    parts.splice(idx, 1);
    setField(field, parts.filter(Boolean).join(", "));
  };

  const submit = () => {
    const e = {};
    if (!form.nombre.trim()) e.nombre = "El nombre es obligatorio";
    if (!form.preparacion.trim()) e.preparacion = "Indica al menos un área de atención";
    if (!form.formacion.trim()) e.formacion = "Indica al menos un enfoque o formación";
    setErrors(e);
    if (Object.keys(e).length) return;
    onSave({
      nombre:       form.nombre.trim(),
      titulo:       form.titulo,
      cedula:       form.cedula.trim() || "Sin cédula registrada",
      preparacion:  form.preparacion.trim(),
      formacion:    form.formacion.trim(),
      terapeuta_id: form.terapeuta_db_id ? parseInt(form.terapeuta_db_id) : null,
    });
  };

  const livePreview = form.nombre.trim() ? form : null;

  const prepCurrent = form.preparacion.split(/,\s*/).map(s => s.trim()).filter(Boolean);
  const formCurrent = form.formacion.split(/,\s*/).map(s => s.trim()).filter(Boolean);
  const COMMON_FORM = ["TCC","DBT","ACT","Gestalt","Mindfulness","Psicoanálisis","Sistémica familiar","Tanatología","Hipnosis clínica","PAPS","Intervención en crisis","Psicoterapia infantil","Psicoterapia de juego","Consejería","Psiquiatría","Terapia breve"];

  return (
    <>
      <div className="drawer-backdrop open" onClick={onClose}></div>
      <div className="form-modal">
        <div className="form-head">
          <div className="form-head-l">
            <div className="form-head-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                {isEdit
                  ? <><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></>
                  : <><circle cx="9" cy="7" r="4"/><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><path d="M19 8v6M22 11h-6"/></>}
              </svg>
            </div>
            <div>
              <h2>{isEdit ? "Editar terapeuta" : "Agregar nuevo terapeuta"}</h2>
              <p>{isEdit ? "Actualiza los datos y guarda los cambios." : "Completa los campos para registrar al terapeuta en el catálogo."}</p>
            </div>
          </div>
          <button className="drawer-close" onClick={onClose} aria-label="Cerrar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>

        <div className="form-body">
          {/* Live preview */}
          <div className="form-preview">
            <div className="form-preview-label">Vista previa</div>
            {livePreview ? (
              <div className="preview-card">
                <Avatar name={form.nombre || "Nuevo"} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="card-name" style={{ fontSize: 15 }}>{form.nombre || "Nombre del terapeuta"}</div>
                  <div className="card-meta">
                    <span className={`titulo-badge ${form.titulo === "Maestría" ? "maestria" : "licenciatura"}`}>
                      {form.titulo === "Maestría" ? "Mtra." : "Lic."}
                    </span>
                    <span className="cedula">{form.cedula || "Cédula pendiente"}</span>
                  </div>
                  {previewAreas.length > 0 && (
                    <div className="area-chips" style={{ marginTop: 8 }}>
                      {previewAreas.map(ak => {
                        const area = window.AREAS[ak];
                        return (
                          <span key={ak} className="area-chip" style={{ "--chip-soft": area.soft, "--chip-color": area.color }}>
                            <AreaIcon areaKey={ak} size={10} stroke={2.4} />
                            {area.label}
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="preview-empty">Escribe el nombre para ver la vista previa</div>
            )}
          </div>

          <div className="form-grid">
            <div className="form-row" style={{ gridColumn: "1 / -1" }}>
              <label>Nombre completo <span className="req">*</span></label>
              <input ref={firstInputRef} className={errors.nombre ? "err" : ""}
                value={form.nombre} onChange={e => setField("nombre", e.target.value)}
                placeholder="Ej. María García López" />
              {errors.nombre && <span className="err-msg">{errors.nombre}</span>}
            </div>

            <div className="form-row">
              <label>Título académico</label>
              <div className="seg">
                <button type="button" className={form.titulo === "Licenciatura" ? "on" : ""}
                  onClick={() => setField("titulo", "Licenciatura")}>Licenciatura</button>
                <button type="button" className={form.titulo === "Maestría" ? "on" : ""}
                  onClick={() => setField("titulo", "Maestría")}>Maestría</button>
              </div>
            </div>

            <div className="form-row">
              <label>Cédula profesional</label>
              <input value={form.cedula} onChange={e => setField("cedula", e.target.value)}
                placeholder="Ej. Lic: 14747476" />
            </div>

            <div className="form-row" style={{ gridColumn: "1 / -1" }}>
              <label>
                Vincular al sistema INTRA
                <span style={{ marginLeft:6, fontSize:'0.72rem', fontWeight:400, color:'#8891B3' }}>
                  — permite preseleccionar al agendar cita
                </span>
              </label>
              <select
                value={form.terapeuta_db_id}
                onChange={e => setField("terapeuta_db_id", e.target.value)}
                style={{ width:'100%', padding:'9px 12px', border:'1.5px solid var(--line)', borderRadius:'var(--radius-sm)', fontSize:14, color:'var(--ink-2)', background:'#fff', outline:'none' }}
              >
                <option value="">— Sin vincular —</option>
                {dbTerapeutas.map(t => {
                  const esMismo = String(t.id) === String(form.terapeuta_db_id);
                  const ocupado  = t.ya_vinculado && !esMismo;
                  return (
                    <option key={t.id} value={t.id} disabled={ocupado}>
                      {t.nombre}{ocupado ? ' (ya vinculado)' : ''}
                    </option>
                  );
                })}
              </select>
            </div>

            <div className="form-row" style={{ gridColumn: "1 / -1" }}>
              <label>Puede atender <span className="req">*</span> <span className="hint">— pulsa para agregar</span></label>
              <div className="chip-input">
                {prepCurrent.map((term, i) => {
                  const ak = window.termArea(term);
                  const area = window.AREAS[ak];
                  return (
                    <span key={i} className="chip-input-item" style={{ background: area.soft, color: area.color }}>
                      <AreaIcon areaKey={ak} size={10} stroke={2.4} />
                      {term}
                      <button onClick={() => removeTermFromField("preparacion", i)}>
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
                      </button>
                    </span>
                  );
                })}
                <input
                  placeholder={prepCurrent.length ? "Otro motivo…" : "Ej. Ansiedad, Trauma…"}
                  onKeyDown={e => {
                    if (e.key === "Enter" && e.currentTarget.value.trim()) {
                      e.preventDefault();
                      addTermToField("preparacion", e.currentTarget.value.trim());
                      e.currentTarget.value = "";
                    }
                  }}
                />
              </div>
              {errors.preparacion && <span className="err-msg">{errors.preparacion}</span>}

              <div className="term-bank">
                <div className="bank-label">Sugerencias por área</div>
                {Object.entries(window.AREAS).map(([key, area]) => (
                  <div key={key} className="bank-row">
                    <span className="bank-area" style={{ color: area.color }}>
                      <AreaIcon areaKey={key} size={11} stroke={2.4} />
                      {area.label}
                    </span>
                    {area.terms.map(term => {
                      const active = prepCurrent.map(s => s.toLowerCase()).includes(term.toLowerCase());
                      return (
                        <button key={term} type="button"
                          className={`bank-chip ${active ? "active" : ""}`}
                          onClick={() => {
                            if (active) {
                              const idx = prepCurrent.findIndex(s => s.toLowerCase() === term.toLowerCase());
                              if (idx >= 0) removeTermFromField("preparacion", idx);
                            } else {
                              addTermToField("preparacion", term);
                            }
                          }}
                          style={active ? { background: area.color, color: "#fff", borderColor: area.color } : {}}>
                          {active ? "✓ " : "+ "}{term}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>

            <div className="form-row" style={{ gridColumn: "1 / -1" }}>
              <label>Formación y enfoques <span className="req">*</span></label>
              <div className="chip-input">
                {formCurrent.map((f, i) => (
                  <span key={i} className="chip-input-item neutral">
                    {f}
                    <button onClick={() => removeTermFromField("formacion", i)}>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
                    </button>
                  </span>
                ))}
                <input
                  placeholder={formCurrent.length ? "Otro enfoque…" : "Ej. TCC, DBT, Mindfulness…"}
                  onKeyDown={e => {
                    if (e.key === "Enter" && e.currentTarget.value.trim()) {
                      e.preventDefault();
                      addTermToField("formacion", e.currentTarget.value.trim());
                      e.currentTarget.value = "";
                    }
                  }}
                />
              </div>
              {errors.formacion && <span className="err-msg">{errors.formacion}</span>}
              <div className="bank-row" style={{ marginTop: 10 }}>
                {COMMON_FORM.map(f => {
                  const active = formCurrent.map(s => s.toLowerCase()).includes(f.toLowerCase());
                  return (
                    <button key={f} type="button" className={`bank-chip ${active ? "active" : ""}`}
                      onClick={() => {
                        if (active) {
                          const idx = formCurrent.findIndex(s => s.toLowerCase() === f.toLowerCase());
                          if (idx >= 0) removeTermFromField("formacion", idx);
                        } else addTermToField("formacion", f);
                      }}>
                      {active ? "✓ " : "+ "}{f}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="form-foot">
          <button className="btn-secondary" onClick={onClose}>Cancelar</button>
          <button className="btn-primary" onClick={submit}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round"><path d="M5 12l5 5L20 7"/></svg>
            {isEdit ? "Guardar cambios" : "Agregar terapeuta"}
          </button>
        </div>
      </div>
    </>
  );
}

// ============ Main App ============
function App() {
  const [therapists, setTherapists] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchCatalogo = () => {
    setLoading(true);
    apiFetch('/api/catalogo/')
      .then(data => setTherapists(data && data.length ? data : window.THERAPISTS))
      .catch(() => setTherapists(window.THERAPISTS))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchCatalogo(); }, []);

  const [query, setQuery] = useState("");
  const [tokens, setTokens] = useState([]);
  const [selectedAreas, setSelectedAreas] = useState(new Set());
  const [titulo, setTitulo] = useState("todos");
  const [openTherapist, setOpenTherapist] = useState(null);
  const [toastMsg, setToastMsg] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editingT, setEditingT] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    window.__toast = (msg) => {
      setToastMsg(msg);
      setTimeout(() => setToastMsg(""), 2400);
    };
  }, []);

  const queryTokens = useMemo(() => {
    const fromInput = expandQuery(query);
    return [...tokens, ...fromInput];
  }, [query, tokens]);

  const commitToken = (t) => {
    const norm = (window.SYNONYMS[t.toLowerCase()] || t).trim();
    if (norm && !tokens.includes(norm)) setTokens([...tokens, norm]);
    setQuery("");
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && query.trim()) { commitToken(query.trim()); }
    if (e.key === "Backspace" && !query && tokens.length) { setTokens(tokens.slice(0, -1)); }
  };

  const removeToken = (i) => setTokens(tokens.filter((_, j) => j !== i));

  const toggleArea = (key) => {
    const next = new Set(selectedAreas);
    if (next.has(key)) next.delete(key); else next.add(key);
    setSelectedAreas(next);
  };

  const openAdd = () => { setEditingT(null); setFormOpen(true); };
  const openEdit = (t) => { setEditingT(t); setFormOpen(true); setOpenTherapist(null); };

  const saveTherapist = async (data) => {
    try {
      if (editingT && editingT.id) {
        await apiFetch(`/api/catalogo/${editingT.id}/`, { method: 'PUT', body: JSON.stringify(data) });
        window.__toast(`${data.nombre.split(" ")[0]} actualizado`);
      } else {
        await apiFetch('/api/catalogo/', { method: 'POST', body: JSON.stringify(data) });
        window.__toast(`${data.nombre.split(" ")[0]} agregado al catálogo`);
      }
      setFormOpen(false);
      setEditingT(null);
      fetchCatalogo();
    } catch(e) {
      alert('Error al guardar. Verifica tu conexión o permisos.');
    }
  };

  const deleteTherapist = async (t) => {
    if (!t.id) return;
    try {
      await apiFetch(`/api/catalogo/${t.id}/`, { method: 'DELETE' });
      window.__toast(`${t.nombre.split(" ")[0]} eliminado`);
      fetchCatalogo();
    } catch(e) {
      alert('Error al eliminar.');
    }
  };

  const results = useMemo(() => {
    let list = therapists.map(t => {
      const s = scoreTherapist(t, queryTokens, selectedAreas);
      return { t, ...s };
    });

    if (titulo !== "todos") {
      list = list.filter(x => titulo === "maestria" ? x.t.titulo === "Maestría" : x.t.titulo === "Licenciatura");
    }

    const hasFilter = queryTokens.length > 0 || selectedAreas.size > 0;
    if (hasFilter) {
      list = list.filter(x => x.score > 0);
      list.sort((a, b) => b.score - a.score || a.t.nombre.localeCompare(b.t.nombre));
    } else {
      list.sort((a, b) => {
        if (a.t.titulo !== b.t.titulo) return a.t.titulo === "Maestría" ? -1 : 1;
        return a.t.nombre.localeCompare(b.t.nombre);
      });
    }
    return list;
  }, [therapists, queryTokens, selectedAreas, titulo]);

  const areaCounts = useMemo(() => {
    const m = {};
    for (const a of Object.keys(window.AREAS)) m[a] = 0;
    let base = therapists;
    if (titulo !== "todos") base = base.filter(t => titulo === "maestria" ? t.titulo === "Maestría" : t.titulo === "Licenciatura");
    for (const t of base) {
      const areas = new Set(window.parsePrep(t.preparacion).map(x => window.termArea(x)));
      for (const a of areas) m[a]++;
    }
    return m;
  }, [therapists, titulo]);

  const totalMaestria = therapists.filter(t => t.titulo === "Maestría").length;
  const totalLic = therapists.filter(t => t.titulo === "Licenciatura").length;
  const hasFilter = queryTokens.length > 0 || selectedAreas.size > 0;

  const quickSuggestions = ["Ansiedad infantil", "Duelo", "Conducta suicida", "Adicciones", "Parejas", "Trauma"];

  if (loading) {
    return (
      <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh', flexDirection:'column', gap:16 }}>
        <div style={{ width:44, height:44, border:'3px solid #E8EEFF', borderTopColor:'#1B53FF', borderRadius:'50%', animation:'spin 0.8s linear infinite' }}></div>
        <p style={{ color:'#5A6388', fontSize:14 }}>Cargando catálogo…</p>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    );
  }

  return (
    <div className="shell">
      <section className="hero">
        <div className="hero-row">
          <div className="hero-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
              <path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
          </div>
          <div style={{ flex: 1, minWidth: 280 }}>
            <h1>Catálogo de Terapeutas</h1>
            <p className="hero-sub">Encuentra al especialista adecuado para cada paciente — describe el motivo de consulta y te mostraremos coincidencias.</p>
            <div className="hero-actions">
              {CAN_EDIT && (
                <button className="hero-btn primary" onClick={openAdd}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
                  Agregar terapeuta
                </button>
              )}
              <div className="hero-pill">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                Actualizado · {new Date().toLocaleDateString("es-MX", { day:"2-digit", month:"long", year:"numeric" })}
              </div>
            </div>
          </div>
          <div className="hero-stats">
            <div className="stat-chip"><span className="n">{therapists.length}</span> Terapeutas</div>
            <div className="stat-chip"><span className="n">{totalMaestria}</span> Maestrías</div>
            <div className="stat-chip accent"><span className="n">{totalLic}</span> Licenciaturas</div>
          </div>
        </div>
      </section>

      <div className="search-wrap">
        <div className="search-card">
          <div className="search-label">
            <span className="dot"></span>
            ¿Qué necesita el paciente?
          </div>
          <div className="search-input-row" onClick={() => inputRef.current?.focus()}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
            {tokens.map((tok, i) => (
              <span key={i} className="token">
                {tok}
                <button onClick={() => removeToken(i)} aria-label="Quitar">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
                </button>
              </span>
            ))}
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKey}
              placeholder={tokens.length ? "Añade otro motivo…" : "ej. ansiedad, duelo, niño con TDAH, conducta suicida…"}
            />
            {(query || tokens.length > 0 || selectedAreas.size > 0) && (
              <button className="clear-btn" onClick={() => { setQuery(""); setTokens([]); setSelectedAreas(new Set()); }} title="Limpiar todo">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            )}
          </div>
          <div className="quick-row">
            <span className="token-hint">Búsquedas rápidas:</span>
            {quickSuggestions.map((s, i) => (
              <button key={i} className="quick-chip" onClick={() => {
                const parts = s.split(/\s+/);
                parts.forEach(p => commitToken(p));
              }}>
                <span>＋</span> {s}
              </button>
            ))}
          </div>
        </div>

        <div className="filter-bar">
          {Object.entries(window.AREAS).map(([key, area]) => {
            const active = selectedAreas.has(key);
            return (
              <button
                key={key}
                className={`area-pill ${active ? "active" : ""}`}
                onClick={() => toggleArea(key)}
                style={active ? { background: area.color, boxShadow: `0 8px 18px -6px ${area.color}66` } : { color: area.color }}
              >
                <span className="ic" style={{ background: active ? "rgba(255,255,255,.22)" : area.soft, color: active ? "#fff" : area.color }}>
                  <AreaIcon areaKey={key} size={11} stroke={2.4} />
                </span>
                {area.label}
                <span className="ct">{areaCounts[key]}</span>
              </button>
            );
          })}

          <div className="spacer"></div>

          <div className="titulo-toggle" role="tablist" aria-label="Filtrar por título">
            <button className={titulo === "todos" ? "on" : ""} onClick={() => setTitulo("todos")}>Todos</button>
            <button className={titulo === "maestria" ? "on" : ""} onClick={() => setTitulo("maestria")}>Maestría</button>
            <button className={titulo === "licenciatura" ? "on" : ""} onClick={() => setTitulo("licenciatura")}>Licenciatura</button>
          </div>
        </div>

        <div className="filter-bar" style={{ marginTop: 10 }}>
          <div className="results-count">
            Mostrando <b>{results.length}</b> {results.length === 1 ? "terapeuta" : "terapeutas"}
            {hasFilter && " coincidentes"}
          </div>
          {hasFilter && (
            <div className="sort-chip">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.39 7.36H22l-6.18 4.49L18.21 22 12 17.27 5.79 22l2.39-8.15L2 9.36h7.61z"/></svg>
              Ordenado por mejor coincidencia
            </div>
          )}
        </div>
      </div>

      <div className="grid" key={`${queryTokens.join("|")}-${[...selectedAreas].join("|")}-${titulo}-${therapists.length}`}>
        {results.length === 0 && (
          <div className="empty">
            <svg className="empty-illu" viewBox="0 0 24 24" fill="none" stroke="#5A6388" strokeWidth="1.2">
              <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
            </svg>
            <h3>Sin coincidencias</h3>
            <p>No hay terapeutas que atiendan exactamente esos motivos. Intenta con términos más amplios o quita algún filtro.</p>
          </div>
        )}
        {results.map((r, i) => (
          <TerapeutaCard
            key={r.t.nombre}
            t={r.t}
            score={r.score}
            hitTerms={r.hitTerms}
            hitAreas={r.hitAreas}
            query={query}
            onOpen={setOpenTherapist}
            delay={Math.min(i * 35, 400)}
          />
        ))}
      </div>

      {CAN_EDIT && (
        <button className="fab" onClick={openAdd} title="Agregar terapeuta">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
        </button>
      )}

      <Drawer
        t={openTherapist}
        onClose={() => setOpenTherapist(null)}
        queryTokens={queryTokens}
        selectedAreas={selectedAreas}
        onEdit={openEdit}
        onDelete={deleteTherapist}
      />

      <TherapistForm
        open={formOpen}
        initial={editingT}
        onClose={() => { setFormOpen(false); setEditingT(null); }}
        onSave={saveTherapist}
      />

      <div className={`toast ${toastMsg ? "show" : ""}`}>
        <span className="check">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3.5" strokeLinecap="round"><path d="M5 12l5 5L20 7"/></svg>
        </span>
        {toastMsg}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
