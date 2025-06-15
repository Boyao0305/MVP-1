import { useState } from "react";

export default function Counter() {
  const [count, setCount] = useState(0);
  return (
    <button
      onClick={() => setCount((c) => c + 1)}
      style={{fontSize: "1.25rem", padding: "0.5rem 1rem"}}
    >
      Count is {count}
    </button>
  );
}
