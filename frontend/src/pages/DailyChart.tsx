import { useEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";

export default function DailyChart({
  labels,
  values,
}: {
  labels: string[];
  values: number[];
}) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!root.current) {
      return;
    }
    const chart = new uPlot(
      {
        width: 640,
        height: 240,
        series: [{}, { stroke: "#2563eb" }],
        axes: [{}, { values: (_u, ticks) => ticks.map((tick) => String(Math.round(Number(tick) / 100))) }],
      },
      [labels.map((_, index) => index), values],
      root.current,
    );
    return () => chart.destroy();
  }, [labels, values]);
  return <div ref={root} />;
}
