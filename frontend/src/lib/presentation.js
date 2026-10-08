export const labels = {
  P1: "Debug",
  P2: "Information",
  P3: "Warning",
  P4: "Error",
  P5: "Critical",
};
export const colors = {
  P1: "#789991",
  P2: "#5b9d9f",
  P3: "#d3a640",
  P4: "#dd865b",
  P5: "#b34d44",
};
export const time = (value) =>
  new Date(value).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
