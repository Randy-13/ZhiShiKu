import { useCallback, useState } from "react";
import type { ActivityEvent } from "../domain";
import { uid } from "../utils/uid";

export function useActivityLog(limit = 50) {
  const [activities, setActivities] = useState<ActivityEvent[]>([]);

  const addActivity = useCallback(
    (event: Omit<ActivityEvent, "id" | "time">) => {
      setActivities((current) => [
        {
          ...event,
          id: uid("activity"),
          time: new Date().toLocaleTimeString(),
        },
        ...current.slice(0, Math.max(0, limit - 1)),
      ]);
    },
    [limit],
  );

  return { activities, addActivity };
}
