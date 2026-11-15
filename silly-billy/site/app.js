const fields = [
  ["overview", "Course overview"],
  ["due_dates", "Due dates"],
  ["lecture_dates", "Lectures and class meetings"],
  ["exam_dates", "Exams"],
  ["grading", "Grading"],
];

const example = {
  overview: ["Introduction to Environmental Science"],
  due_dates: ["Lab report due September 28", "Final project due December 4"],
  lecture_dates: ["Mondays and Wednesdays, 10:00–11:15 a.m."],
  exam_dates: ["Midterm on October 14", "Final on December 11"],
  grading: ["Labs 25%", "Project 25%", "Midterm 20%", "Final 30%"],
};

const form = document.querySelector("#upload-form");
const input = document.querySelector("#syllabus");
const status = document.querySelector("#status");
const summary = document.querySelector("#summary");
const exampleButton = document.querySelector("#example");
const exampleLabel = document.querySelector("#example-label");
const submit = form.querySelector("button");
const retry = document.querySelector("#retry");
let busy = false;

function clearResults() {
  summary.replaceChildren();
  summary.hidden = true;
  exampleLabel.hidden = true;
  retry.hidden = true;
}

function setBusy(value) {
  busy = value;
  input.disabled = submit.disabled = exampleButton.disabled = retry.disabled = value;
  form.setAttribute("aria-busy", String(value));
}

function validSummary(data) {
  return data !== null && typeof data === "object" && !Array.isArray(data) &&
    Object.keys(data).length === fields.length && fields.every(([key]) =>
      Array.isArray(data[key]) && data[key].length <= 50 && data[key].every(entry =>
        typeof entry === "string" && entry.length <= 2000 &&
        /^[^\[\]\r\n]+(?: \[Page [1-9][0-9]*\])+$/.test(entry)));
}

const knownErrorMessages = new Set([
  "Choose a PDF syllabus.", "Choose a PDF no larger than 25 MB.",
  "The selected file is not a readable PDF.",
  "Choose a PDF without password protection.",
  "This PDF has no selectable text. Try a text-based PDF.",
  "PDF ingestion is unavailable. Please try again later.",
  "Summary generation is unavailable. Please try again later.",
]);

function failure(message) {
  status.textContent = message;
  retry.hidden = false;
}

function showSummary(data, isExample) {
  summary.replaceChildren();
  for (const [key, label] of fields) {
    const title = document.createElement("dt");
    const description = document.createElement("dd");
    title.textContent = label;
    if (data[key]?.length) {
      const list = document.createElement("ul");
      for (const entry of data[key]) {
        const item = document.createElement("li");
        item.textContent = entry;
        list.append(item);
      }
      description.append(list);
    } else {
      description.textContent = "No details found in retrieved syllabus evidence";
    }
    summary.append(title, description);
  }
  exampleLabel.hidden = !isExample;
  summary.hidden = false;
  status.hidden = false;
  status.textContent = isExample ? "Sample course details." : "Summary ready.";
}

exampleButton.addEventListener("click", () => {
  if (busy) return;
  clearResults();
  showSummary(example, true);
});

input.addEventListener("change", () => {
  if (busy) return;
  clearResults();
  status.textContent = input.files[0] ? `Selected: ${input.files[0].name}. Ready to summarize.` :
    "Choose a PDF syllabus.";
});

retry.addEventListener("click", () => form.requestSubmit());

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  clearResults();
  const file = input.files[0];
  if (!file || !/\.pdf$/i.test(file.name)) {
    status.textContent = "Choose a PDF syllabus.";
    return;
  }
  if (file.size === 0) {
    status.textContent = "Choose a nonempty PDF with selectable text.";
    return;
  }
  if (file.size > 25 * 1024 * 1024) {
    status.textContent = "Choose a PDF no larger than 25 MB.";
    return;
  }
  if (location.protocol === "file:") {
    status.textContent = "Start the Python server to upload a syllabus. You can view an example here.";
    return;
  }

  // Capture the file before disabling its control (disabled inputs are omitted by FormData).
  const body = new FormData();
  body.append("syllabus", file);
  setBusy(true);
  status.textContent = `Reading ${file.name}? This may take a while.`;
  try {
    const response = await fetch("/api/summarize", { method: "POST", body });
    let data;
    try {
      data = await response.json();
    } catch {
      failure("The server returned an unreadable response. Try again, or check that the Python server is running.");
      return;
    }
    if (!response.ok) {
      const safeMessage = data && knownErrorMessages.has(data.error) &&
        typeof data.error === "string" && data.error.trim() && data.error.length <= 500;
      failure(safeMessage ? data.error : "The syllabus could not be summarized. Try again, or contact the server administrator.");
      return;
    }
    if (!validSummary(data)) {
      failure("The server returned an invalid summary. Try again, or contact the server administrator.");
      return;
    }
    showSummary(data, false);
    status.textContent = `Summary ready for ${file.name}. Check the original syllabus for full details.`;
  } catch {
    failure("Could not reach the server. Check your connection and that the Python server is running, then try again.");
  } finally {
    setBusy(false);
  }
});
