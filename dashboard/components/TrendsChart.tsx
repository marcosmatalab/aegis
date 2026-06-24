"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useLocale } from "@/lib/i18n/LocaleProvider";
import type { TrendPoint } from "@/lib/trend";
import { Card } from "./Card";

// A trend needs >= 2 REAL runs. With 0 or 1, render an explicit absent note — never a
// single floating point or a faked line. connectNulls=false leaves gaps for missing
// metrics rather than interpolating across them.
export function TrendsChart({ points }: { points: TrendPoint[] }) {
  const { t } = useLocale();
  if (points.length < 2) {
    return (
      <Card title={t("trends.title")}>
        <p style={{ margin: 0, color: "#9aa0aa" }}>
          {points.length === 0 ? t("trends.noRuns") : t("trends.needTwoRuns")}
        </p>
      </Card>
    );
  }
  return (
    <Card title={t("trends.title")} subtitle={t("trends.runsSubtitle", { n: points.length })}>
      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer>
          <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: -8 }}>
            <CartesianGrid stroke="#22262e" />
            <XAxis dataKey="label" tick={{ fill: "#9aa0aa", fontSize: 11 }} />
            <YAxis domain={[0, 1]} tick={{ fill: "#9aa0aa", fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                background: "#14171d",
                border: "1px solid #2c313a",
                color: "#e6e6e6",
              }}
            />
            <Legend />
            <Line type="monotone" dataKey="overall" stroke="#5ee08a" connectNulls={false} />
            <Line type="monotone" dataKey="l1" stroke="#7aa2f7" connectNulls={false} />
            <Line type="monotone" dataKey="l2" stroke="#e0b15e" connectNulls={false} />
            <Line type="monotone" dataKey="l3" stroke="#bb9af7" connectNulls={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
