// VO2 Max gauge showing classification vs age/gender peer group
// Classifications: Garmin / Cooper Institute standard

// Lower bounds for each category (ml/kg/min)
const THRESHOLDS = {
  male: [
    { ages: "20–29", fair: 41.7, good: 45.4, excellent: 51.1, superior: 55.4 },
    { ages: "30–39", fair: 40.5, good: 44.0, excellent: 48.3, superior: 54.0 },
    { ages: "40–49", fair: 38.5, good: 42.4, excellent: 46.4, superior: 52.5 },
    { ages: "50–59", fair: 35.6, good: 39.2, excellent: 43.4, superior: 48.9 },
    { ages: "60–69", fair: 32.3, good: 35.5, excellent: 39.5, superior: 45.7 },
    { ages: "70–79", fair: 29.4, good: 32.3, excellent: 36.7, superior: 42.1 },
  ],
  female: [
    { ages: "20–29", fair: 36.1, good: 39.5, excellent: 43.9, superior: 49.6 },
    { ages: "30–39", fair: 34.4, good: 37.8, excellent: 42.4, superior: 47.4 },
    { ages: "40–49", fair: 33.0, good: 36.3, excellent: 39.7, superior: 45.3 },
    { ages: "50–59", fair: 30.1, good: 33.0, excellent: 36.7, superior: 41.1 },
    { ages: "60–69", fair: 27.5, good: 30.0, excellent: 33.0, superior: 37.8 },
    { ages: "70–79", fair: 25.9, good: 28.1, excellent: 30.9, superior: 36.7 },
  ],
} as const;

type Gender = keyof typeof THRESHOLDS;
type AgeRow = (typeof THRESHOLDS.male)[number];

function getAgeRow(age: number, gender: Gender): AgeRow {
  const rows = THRESHOLDS[gender] as unknown as AgeRow[];
  const idx = Math.max(0, Math.min(5, Math.floor((Math.max(20, Math.min(79, age)) - 20) / 10)));
  return rows[idx];
}

const CATEGORIES = [
  { key: "Poor",      color: "#ef4444" },
  { key: "Fair",      color: "#f97316" },
  { key: "Good",      color: "#84cc16" },
  { key: "Excellent", color: "#22d3ee" },
  { key: "Superior",  color: "#8b5cf6" },
] as const;

type CategoryKey = (typeof CATEGORIES)[number]["key"];

function classify(vo2: number, t: AgeRow): CategoryKey {
  if (vo2 >= t.superior) return "Superior";
  if (vo2 >= t.excellent) return "Excellent";
  if (vo2 >= t.good) return "Good";
  if (vo2 >= t.fair) return "Fair";
  return "Poor";
}

// ── SVG gauge geometry ────────────────────────────────────────────────────────
// The arc spans 240° clockwise from lower-left (150°) to lower-right (30°/390°)
// through the top (270°), using standard SVG angles (CW from positive x-axis).
const CX = 100, CY = 98, R = 74, SW = 13;
const START = 150, TOTAL_SWEEP = 240;
const GAP = 2.0; // angular gap between segment boundaries

function polar(deg: number, r: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: CX + r * Math.cos(rad), y: CY + r * Math.sin(rad) };
}

function arcPath(a1: number, a2: number, r: number): string {
  const p1 = polar(a1, r);
  const p2 = polar(a2, r);
  const large = a2 - a1 > 180 ? 1 : 0;
  return `M ${p1.x.toFixed(2)} ${p1.y.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
}

function valToAngle(v: number, min: number, max: number): number {
  return START + ((v - min) / (max - min)) * TOTAL_SWEEP;
}

// ── Component ─────────────────────────────────────────────────────────────────
interface Props {
  vo2max: number | null;
  goal: number;
  age: number;
  gender?: Gender;
}

export default function Vo2GaugeCard({ vo2max, goal, age, gender = "male" }: Props) {
  const t = getAgeRow(age, gender);

  // Display range: extends the Poor floor below fair and a buffer above superior
  const range = t.superior - t.fair;
  const displayMin = Math.floor(t.fair - range * 0.55);
  const displayMax = Math.ceil(t.superior + range * 0.42);
  const displayRange = displayMax - displayMin;

  // Boundary angles for each category threshold
  const ba = {
    fair:      valToAngle(t.fair,      displayMin, displayMax),
    good:      valToAngle(t.good,      displayMin, displayMax),
    excellent: valToAngle(t.excellent, displayMin, displayMax),
    superior:  valToAngle(t.superior,  displayMin, displayMax),
    end:       START + TOTAL_SWEEP,
  };

  // Arc segments (first starts flush at arc start, last ends flush at arc end)
  const segments = [
    { key: "Poor",      color: "#ef4444", from: START,              to: ba.fair - GAP      },
    { key: "Fair",      color: "#f97316", from: ba.fair + GAP,      to: ba.good - GAP      },
    { key: "Good",      color: "#84cc16", from: ba.good + GAP,      to: ba.excellent - GAP },
    { key: "Excellent", color: "#22d3ee", from: ba.excellent + GAP, to: ba.superior - GAP  },
    { key: "Superior",  color: "#8b5cf6", from: ba.superior + GAP,  to: ba.end             },
  ];

  const categoryKey   = vo2max !== null ? classify(vo2max, t) : null;
  const categoryColor = categoryKey ? CATEGORIES.find(c => c.key === categoryKey)!.color : null;

  // Clamp indicator angle within the arc
  const indicatorAngle = vo2max !== null
    ? Math.max(START + 0.5, Math.min(ba.end - 0.5, valToAngle(vo2max, displayMin, displayMax)))
    : null;
  const indicatorPos = indicatorAngle !== null ? polar(indicatorAngle, R) : null;

  // Threshold tick labels on the inner edge of the arc
  const ticks = [
    { value: t.fair,      label: t.fair.toString()      },
    { value: t.good,      label: t.good.toString()      },
    { value: t.excellent, label: t.excellent.toString() },
    { value: t.superior,  label: t.superior.toString()  },
  ].map(tk => {
    const angle = valToAngle(tk.value, displayMin, displayMax);
    const inner = polar(angle, R - SW / 2 - 10);
    return { ...tk, angle, x: inner.x, y: inner.y };
  });

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      {/* Card header */}
      <div className="flex items-start justify-between mb-1">
        <div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">VO₂ Max</h3>
          <p className="text-xs text-gray-400 mt-0.5">vs. {gender}s age {t.ages}</p>
        </div>
        <span className="text-xs text-gray-400">
          Goal: <span className="text-green-500 font-medium">{goal}+</span>
        </span>
      </div>

      {/* Gauge SVG */}
      <div className="relative">
        <svg viewBox="0 0 200 160" className="w-full">
          {/* Background track */}
          <path
            d={arcPath(START, START + TOTAL_SWEEP, R)}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={SW}
            strokeLinecap="round"
            className="dark:stroke-gray-700"
          />

          {/* Colored segments */}
          {segments.map(seg => (
            <path
              key={seg.key}
              d={arcPath(seg.from, seg.to, R)}
              fill="none"
              stroke={seg.color}
              strokeWidth={SW}
              strokeLinecap="round"
            />
          ))}

          {/* Threshold tick labels */}
          {ticks.map(tk => (
            <text
              key={tk.value}
              x={tk.x}
              y={tk.y + 3}
              textAnchor="middle"
              fontSize="7"
              fill="#9ca3af"
              fontWeight="500"
            >
              {tk.label}
            </text>
          ))}

          {/* Indicator dot */}
          {indicatorPos && categoryColor && (
            <>
              <circle
                cx={indicatorPos.x}
                cy={indicatorPos.y}
                r={SW / 2 + 2}
                fill="white"
                className="dark:fill-gray-800"
              />
              <circle
                cx={indicatorPos.x}
                cy={indicatorPos.y}
                r={SW / 2 - 1}
                fill={categoryColor}
              />
              <circle
                cx={indicatorPos.x}
                cy={indicatorPos.y}
                r={SW / 2 + 2}
                fill="none"
                stroke={categoryColor}
                strokeWidth={2}
              />
            </>
          )}

          {/* Center: value */}
          {vo2max !== null ? (
            <>
              <text
                x={CX}
                y={90}
                textAnchor="middle"
                fontSize="34"
                fontWeight="700"
                fill={categoryColor ?? "#111827"}
              >
                {vo2max.toFixed(0)}
              </text>
              <text x={CX} y={107} textAnchor="middle" fontSize="10" fill="#9ca3af">
                ml/kg/min
              </text>
            </>
          ) : (
            <text x={CX} y={98} textAnchor="middle" fontSize="12" fill="#9ca3af">
              No data yet
            </text>
          )}

          {/* Category label below arc */}
          {categoryKey && categoryColor && (
            <text
              x={CX}
              y={150}
              textAnchor="middle"
              fontSize="13"
              fontWeight="600"
              fill={categoryColor}
            >
              {categoryKey}
            </text>
          )}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex justify-center gap-3 flex-wrap mt-0">
        {CATEGORIES.map(cat => {
          const isCurrent = cat.key === categoryKey;
          const isGoalZone = cat.key === "Excellent" || cat.key === "Superior";
          return (
            <div
              key={cat.key}
              className={`flex items-center gap-1 text-xs ${isCurrent ? "font-bold" : "text-gray-400 dark:text-gray-500"}`}
            >
              <div
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: cat.color, opacity: isCurrent ? 1 : 0.5 }}
              />
              <span style={isCurrent ? { color: cat.color } : undefined}>
                {cat.key}
                {isGoalZone && !isCurrent && (
                  <span className="text-gray-300 dark:text-gray-600"> ★</span>
                )}
              </span>
            </div>
          );
        })}
      </div>

      {/* Threshold bands summary */}
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
        {[
          { label: "Poor",      range: `< ${t.fair}`,                                color: "#ef4444" },
          { label: "Fair",      range: `${t.fair} – ${t.good - 0.1}`,               color: "#f97316" },
          { label: "Good",      range: `${t.good} – ${t.excellent - 0.1}`,          color: "#84cc16" },
          { label: "Excellent", range: `${t.excellent} – ${t.superior - 0.1}`,      color: "#22d3ee" },
          { label: "Superior",  range: `≥ ${t.superior}`,                           color: "#8b5cf6" },
        ].map(row => (
          <div key={row.label} className={`flex items-center gap-1.5 ${row.label === categoryKey ? "opacity-100" : "opacity-50"}`}>
            <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: row.color }} />
            <span className="text-xs text-gray-500 dark:text-gray-400">
              <span className="font-medium" style={row.label === categoryKey ? { color: row.color } : undefined}>
                {row.label}
              </span>{" "}
              {row.range}
            </span>
          </div>
        ))}
        <div className="flex items-center gap-1.5 opacity-50">
          <div className="w-1.5 h-1.5 rounded-full flex-shrink-0 bg-green-500" />
          <span className="text-xs text-gray-500 dark:text-gray-400">
            <span className="font-medium text-green-500">Goal</span> ≥ {goal}
          </span>
        </div>
      </div>

      <p className="text-xs text-gray-400 text-center mt-3">
        Garmin/Cooper Institute · {gender}s {t.ages}
      </p>
    </div>
  );
}
