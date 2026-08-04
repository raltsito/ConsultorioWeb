// Datos de terapeutas extraídos del Excel
window.THERAPISTS = [
  { nombre: "Benjamín Enrique Villagómez Castellanos", cedula: "Lic: 13696789 Mtra: En trámite", preparacion: "Conducta suicida, Estrés, Ansiedad, Depresión, Violencia, TLP, Bulimia, Anorexia, Psicología organizacional, Crisis, Tanatología, Trauma, TOC", formacion: "DBT, ACT, TCC, FAP, AC, MBSR, MBCT, Mindfulness, Habilidades DBT, PAPS e Intervención en crisis", titulo: "Maestría" },
  { nombre: "Maricela Sena García", cedula: "Supervisada Arcadio: 12195628", preparacion: "Estrés, Ansiedad, Depresión, Hipnosis clínica", formacion: "Hipnosis clínica, TCC y DBT", titulo: "Licenciatura" },
  { nombre: "Rosa Elena Macías Ruiz", cedula: "Lic: 14747476", preparacion: "Estrés, Ansiedad, Depresión, Tanatología", formacion: "TCC y Tanatología", titulo: "Licenciatura" },
  { nombre: "Daniel Salazar Salazar", cedula: "Lic: 13951258", preparacion: "Estrés, Ansiedad, Depresión, Violencia, Adicciones, Crisis", formacion: "TCC, PAPS e Intervención en crisis", titulo: "Licenciatura" },
  { nombre: "Perla Paulina Realme Nájera", cedula: "Lic: 13978150", preparacion: "Infantil, Crianza, Salud sexual", formacion: "ACT, TCC, PAPS, Intervención en crisis, Psicoterapia infantil, Psicoterapia de juego", titulo: "Licenciatura" },
  { nombre: "María Idalia Torres Padilla", cedula: "Lic: 8859960 Mtra: En trámite", preparacion: "Estrés, Ansiedad, Depresión, Parejas, Grupal, Violencia, Salud sexual", formacion: "TCC", titulo: "Maestría" },
  { nombre: "Daniela Sarmiento Padilla", cedula: "Lic: 14436825 Mtra: En trámite", preparacion: "Estrés, Ansiedad, Depresión, Familiar, Violencia, Tanatología, Trauma", formacion: "Sistémica familiar, Tanatología", titulo: "Maestría" },
  { nombre: "Alisson Dibenhi Bermea Valdés", cedula: "Supervisada Arcadio: 12195628", preparacion: "Estrés, Ansiedad, Depresión, Violencia, Adicciones, Trauma, Neurodesarrollo, TOC", formacion: "Tanatología, TCC, Mindfulness, DBT", titulo: "Licenciatura" },
  { nombre: "Francisca Esmeralda Colunga Martínez", cedula: "Lic: 0523003260", preparacion: "Infantil, Crianza", formacion: "TCC, Psicoterapia infantil, Psicoterapia de juego", titulo: "Licenciatura" },
  { nombre: "Guadalupe Fabiola Fragoso Espinosa", cedula: "Lic: 14935515 Mtra: En curso", preparacion: "Estrés, Ansiedad, Depresión, Tanatología", formacion: "Psicoanalisis, TCC, Tanatología, Terapia breve", titulo: "Licenciatura" },
  { nombre: "Rosa María Gomez García", cedula: "Lic: 0525002840", preparacion: "Estrés, Ansiedad, Depresión, Tanatología", formacion: "Tanatología y TCC", titulo: "Licenciatura" },
  { nombre: "José Arcadio González Aguilar", cedula: "Lic: 12195628 Mtra: 13221359", preparacion: "Estrés, Ansiedad, Depresión, Violencia, Trauma, Crisis, Conducta Suicida, TLP, Burn Out, Infantil, TOC", formacion: "Gestalt, TCC, Tanatología, PAPS", titulo: "Maestría" },
  { nombre: "David Bermejo Jiménez", cedula: "Supervisado Arcadio: 12195628", preparacion: "Estrés, Ansiedad, Depresión", formacion: "Gestalt", titulo: "Licenciatura" },
  { nombre: "Javier Enrique Martínez Becerra", cedula: "Lic: 0518000588", preparacion: "Estrés, Ansiedad, Depresión, Trauma, Crisis, Adicciones, TLP, Violencia, Conducta Suicida, TOC", formacion: "PAPS, Mindfulness, TCC", titulo: "Licenciatura" },
  { nombre: "Gloria Sarmiento Vasquez", cedula: "Supervisada Arcadio: 12195628", preparacion: "Estrés, Ansiedad, Depresión", formacion: "TCC", titulo: "Licenciatura" },
  { nombre: "Yadira Lucía Sánchez Robles", cedula: "Lic: 2745766 Mtra: 14908716", preparacion: "Estrés, Ansiedad, Depresión, Violencia", formacion: "TCC", titulo: "Maestría" },
  { nombre: "Marisol Guadalupe Cepeda Soto", cedula: "Sin cédula registrada", preparacion: "Consejería", formacion: "Consejería", titulo: "Licenciatura" },
  { nombre: "Enrique Isaí Luna Jimenez", cedula: "Lic: 13229043", preparacion: "Psiquiatría", formacion: "Psiquiatría", titulo: "Licenciatura" },
];

// Categorización por áreas clínicas — cada término "preparacion" mapea a un área.
// iconPath = SVG path data, drawn inside a 24x24 viewBox.
window.AREAS = {
  adultos:      { label: "Adultos",           iconKey: "brain",    color: "#1B53FF", soft: "#E8EEFF", terms: ["Estrés","Ansiedad","Depresión","Burn Out","TLP","TOC","Bulimia","Anorexia","Psicología organizacional"] },
  trauma:       { label: "Trauma & Crisis",   iconKey: "bolt",     color: "#DC2626", soft: "#FEE7E7", terms: ["Trauma","Crisis","Conducta Suicida","Conducta suicida","Adicciones"] },
  violencia:    { label: "Violencia",         iconKey: "shield",   color: "#B45309", soft: "#FEF1D6", terms: ["Violencia"] },
  familia:      { label: "Familia & Parejas", iconKey: "users",    color: "#7C3AED", soft: "#EFE6FE", terms: ["Familiar","Parejas","Grupal","Crianza"] },
  infantil:     { label: "Infantil",          iconKey: "child",    color: "#0D9488", soft: "#D6F3EF", terms: ["Infantil","Neurodesarrollo"] },
  adolescencia: { label: "Adolescencia", iconKey: "youth", color: "#0891B2", soft: "#CFFAFE", terms: ["Adolescencia","Adolescente","Adolescentes"] },
  sexual:       { label: "Salud Sexual",      iconKey: "heart",    color: "#DB2777", soft: "#FCE2EF", terms: ["Salud sexual"] },
  tanatologia:  { label: "Tanatología",       iconKey: "leaf",     color: "#4338CA", soft: "#E2E1FB", terms: ["Tanatología"] },
  especializado:{ label: "Especializado",     iconKey: "sparkles", color: "#475569", soft: "#E5E9EF", terms: ["Hipnosis clínica","Psiquiatría","Consejería"] },
};

// SVG icons (Lucide-style outline). Renders inside a 24x24 viewBox.
window.ICONS = {
  brain: '<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44A2.5 2.5 0 0 1 4.5 17 2.5 2.5 0 0 1 3 14.5a2.5 2.5 0 0 1 1-2 2.5 2.5 0 0 1 0-3.5 2.5 2.5 0 0 1-1-2A2.5 2.5 0 0 1 7 4.5 2.5 2.5 0 0 1 9.5 2z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44A2.5 2.5 0 0 0 19.5 17 2.5 2.5 0 0 0 21 14.5a2.5 2.5 0 0 0-1-2 2.5 2.5 0 0 0 0-3.5 2.5 2.5 0 0 0 1-2A2.5 2.5 0 0 0 17 4.5 2.5 2.5 0 0 0 14.5 2z"/>',
  bolt: '<path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  child: '<circle cx="12" cy="8" r="4"/><path d="M6 22v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/><path d="M10 8h.01M14 8h.01"/>',
  heart: '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
  leaf: '<path d="M11 20A7 7 0 0 1 4 13c0-5 4-9 9-9 4 0 7 3 7 7 0 5-4 9-9 9z"/><path d="M2 22s2-3 6-6 8-4 8-4"/>',
  sparkles: '<path d="M12 2l2 7 7 2-7 2-2 7-2-7-7-2 7-2z"/>',
  youth: '<path d="M12 22v-4"/><path d="M8 22v-5a4 4 0 0 1 4-4h0a4 4 0 0 1 4 4v5"/><circle cx="12" cy="7" r="4"/>',
};

// Mapa rápido término → área-key
window.TERM_TO_AREA = (() => {
  const m = {};
  for (const [key, area] of Object.entries(window.AREAS)) {
    for (const t of area.terms) m[t.toLowerCase()] = key;
  }
  return m;
})();

// Sinónimos / términos coloquiales que la recepción podría escribir
window.SYNONYMS = {
  // ── Depresión ──
  "triste":           "Depresión",
  "tristeza":         "Depresión",
  "decaído":          "Depresión",
  "decaida":          "Depresión",
  "sin ganas":        "Depresión",
  "deprimido":        "Depresión",
  "deprimida":        "Depresión",
  "depresion":        "Depresión",

  // ── Ansiedad ──
  "nervios":          "Ansiedad",
  "nervioso":         "Ansiedad",
  "nerviosa":         "Ansiedad",
  "panico":           "Ansiedad",
  "pánico":           "Ansiedad",
  "miedo":            "Ansiedad",
  "preocupado":       "Ansiedad",
  "preocupada":       "Ansiedad",
  "ansiedad":         "Ansiedad",

  // ── Estrés / Burn Out ──
  "estres":           "Estrés",
  "agotado":          "Burn Out",
  "agotada":          "Burn Out",
  "agotamiento":      "Burn Out",
  "trabajo":          "Burn Out",
  "burnout":          "Burn Out",
  "quemado":          "Burn Out",

  // ── Conducta Suicida ──
  "suicidio":         "Conducta Suicida",
  "suicida":          "Conducta Suicida",
  "ideación":         "Conducta Suicida",
  "ideacion":         "Conducta Suicida",
  "quitarse la vida": "Conducta Suicida",
  "autolesión":       "Conducta Suicida",
  "autolesion":       "Conducta Suicida",

  // ── Adicciones ──
  "alcohol":          "Adicciones",
  "alcoholismo":      "Adicciones",
  "droga":            "Adicciones",
  "drogas":           "Adicciones",
  "cocaina":          "Adicciones",
  "cocaína":          "Adicciones",
  "marihuana":        "Adicciones",
  "apuestas":         "Adicciones",
  "ludopatía":        "Adicciones",
  "ludopatia":        "Adicciones",

  // ── Tanatología ──
  "duelo":            "Tanatología",
  "muerte":           "Tanatología",
  "perdida":          "Tanatología",
  "pérdida":          "Tanatología",
  "luto":             "Tanatología",
  "falleció":         "Tanatología",
  "fallecio":         "Tanatología",
  "fallecimiento":    "Tanatología",

  // ── Violencia ──
  "abuso":            "Violencia",
  "maltrato":         "Violencia",
  "golpes":           "Violencia",
  "agresión":         "Violencia",
  "agresion":         "Violencia",
  "acoso":            "Violencia",

  // ── Parejas ──
  "pareja":           "Parejas",
  "matrimonio":       "Parejas",
  "marital":          "Parejas",
  "divorcio":         "Parejas",
  "separación":       "Parejas",
  "separacion":       "Parejas",

  // ── Familiar / Crianza ──
  "familia":          "Familiar",
  "padres":           "Familiar",
  "hermanos":         "Familiar",
  "crianza":          "Crianza",
  "hijos":            "Crianza",

  // ── Infantil / Neurodesarrollo ──
  "niño":             "Infantil",
  "niña":             "Infantil",
  "niños":            "Infantil",
  "menor":            "Infantil",
  "pediatrico":       "Infantil",
  "pediátrico":       "Infantil",
  "tdah":             "Neurodesarrollo",
  "autismo":          "Neurodesarrollo",
  "tea":              "Neurodesarrollo",

  // ── Adolescencia ──
"adolescente":  "Adolescencia",
"adolescentes": "Adolescencia",
"puberto":      "Adolescencia",

  // ── TLP ──
  "trastorno límite": "TLP",
  "trastorno limite": "TLP",
  "borderline":       "TLP",

  // ── TOC ──
  "obsesivo":           "TOC",
  "obsesivo compulsivo":"TOC",
  "obsesiva":           "TOC",
  "manías":             "TOC",
  "manias":             "TOC",

  // ── Trastornos alimenticios ──
  "comer":            "Bulimia",
  "vomitar":          "Bulimia",
  "alimentaria":      "Anorexia",
  "alimenticia":      "Anorexia",
  "no come":          "Anorexia",
  "no comer":         "Anorexia",

  // ── Salud sexual ──
  "sexual":           "Salud sexual",
  "sexualidad":       "Salud sexual",
  "disfunción":       "Salud sexual",
  "disfuncion":       "Salud sexual",
  "intimidad":        "Salud sexual",
};

// Devuelve lista de términos (preparación) de un terapeuta
window.parsePrep = (s) => s.split(/[,;]+/).map(x => x.trim()).filter(Boolean);

// Asigna área a un término
window.termArea = (term) => window.TERM_TO_AREA[term.toLowerCase()] || "especializado";

// Color/iniciales de avatar — gradiente determinístico por nombre
window.avatarFor = (name) => {
  const palettes = [
    ["#1B53FF","#7C3AED"], ["#0EA5E9","#1B53FF"], ["#DB2777","#7C3AED"],
    ["#0D9488","#1B53FF"], ["#F59E0B","#DC2626"], ["#7C3AED","#DB2777"],
    ["#1B53FF","#0EA5E9"], ["#4338CA","#0D9488"], ["#DC2626","#F59E0B"],
    ["#0D9488","#4338CA"], ["#1B53FF","#DC2626"], ["#7C3AED","#1B53FF"],
  ];
  let h = 0; for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  const p = palettes[h % palettes.length];
  const parts = name.trim().split(/\s+/);
  const initials = (parts[0][0] + (parts[parts.length-1][0] || "")).toUpperCase();
  return { initials, gradient: `linear-gradient(135deg, ${p[0]} 0%, ${p[1]} 100%)`, c1: p[0], c2: p[1] };
};
