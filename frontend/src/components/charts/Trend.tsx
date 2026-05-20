"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type TrendPoint = {
  date: string;
  opens: number;
  clicks: number;
  delivered?: number;
  unsubscribes?: number;
  spams?: number;
};

export function Trend({ data }: { data: TrendPoint[] }) {
  return (
    <div className="h-[260px] w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%" minHeight={260}>
        <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{
              borderRadius: 14,
              border: "1px solid rgba(0,0,0,0.08)",
              boxShadow: "0 20px 60px -30px rgba(0,0,0,0.4)",
            }}
          />
          <Line type="monotone" dataKey="opens" stroke="var(--brand-blue)" strokeWidth={3} dot={false} />
          <Line type="monotone" dataKey="clicks" stroke="var(--brand-yellow)" strokeWidth={3} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

