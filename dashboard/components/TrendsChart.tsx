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

import type { TrendPoint } from "@/lib/trend";
import { Card } from "./Card";

// A trend needs >= 2 REAL runs. With 0 or 1, render an explicit absent note — never a
// single floating point or a faked line. connectNulls=false leaves gaps for missing
// metrics rather than interpolating across them.
export function TrendsChart({ points }: { points: TrendPoint[] }) {
  if (points.length < 2) {
    return (
      <Card title="Trends (across eval runs)">
        <p style={{ margin: 0, color: "#9aa0aa" }}>
          {points.length === 0
            ? "No eval runs yet."
            : "Single eval run — no trend yet (a trend line is never drawn for fewer than two real runs)."}
        </p>
      </Card>
    );
  }
  return (
    <Card title="Trends (across eval runs)" subtitle={`${points.length} runs`}>
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
