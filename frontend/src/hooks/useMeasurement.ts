export type MeasurementSystem = "imperial" | "metric";

export function convertWeight(lbs: number, system: MeasurementSystem): number {
  return system === "metric" ? Math.round(lbs * 0.453592 * 10) / 10 : Math.round(lbs * 10) / 10;
}

export function convertHeight(inches: number, system: MeasurementSystem): string {
  if (system === "metric") {
    return `${Math.round(inches * 2.54)} cm`;
  }
  const ft = Math.floor(inches / 12);
  const inch = Math.round(inches % 12);
  return `${ft}'${inch}"`;
}

export function weightUnit(system: MeasurementSystem): string {
  return system === "metric" ? "kg" : "lbs";
}

export function heightLabel(inches: number | null, system: MeasurementSystem): string {
  if (!inches) return "—";
  return convertHeight(inches, system);
}
