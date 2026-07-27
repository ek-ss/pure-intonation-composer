let latestJob = 0;

self.onmessage = async event => {
  const { job, body } = event.data;
  latestJob = Math.max(latestJob, job);
  try {
    const response = await fetch("/api/prime-limit/explore", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
    if (job === latestJob) self.postMessage({ job, data });
  } catch (error) {
    if (job === latestJob) self.postMessage({ job, error: error instanceof Error ? error.message : "Search failed" });
  }
};
