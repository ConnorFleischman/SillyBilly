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
      description.textContent = "No details found.";
    }
    summary.append(title, description);
  }
  exampleLabel.hidden = !isExample;
  summary.hidden = false;
  status.hidden = false;
  status.textContent = isExample ? "Sample course details." : "Summary ready.";
}

exampleButton.addEventListener("click", () => showSummary(example, true));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  summary.hidden = true;
  exampleLabel.hidden = true;
  status.hidden = false;

  if (input.files[0].size > 25 * 1024 * 1024) {
    status.textContent = "Choose a PDF no larger than 25 MB.";
    return;
  }
  if (location.protocol === "file:") {
    status.textContent = "Start the Python server to upload a syllabus. You can view an example here.";
    return;
  }

  submit.disabled = true;
  exampleButton.disabled = true;
  status.textContent = "Reading your syllabus…";
  try {
    const response = await fetch("/api/summarize", { method: "POST", body: new FormData(form) });
    const data = await response.json();
    if (!response.ok) {
      status.textContent = data.error || "The syllabus could not be summarized.";
      return;
    }
    showSummary(data, false);
  } catch {
    status.textContent = "Could not get a summary. Check that the Python server is running and try again.";
  } finally {
    submit.disabled = false;
    exampleButton.disabled = false;
  }
});
