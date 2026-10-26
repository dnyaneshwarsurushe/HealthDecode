
const fileInput = document.getElementById("pdfFile");

if (fileInput) {
    fileInput.addEventListener("change", function () {
        const file = this.files[0];

        if (file) {
            if (file.type !== "application/pdf") {
                alert("Please select a PDF file.");
                this.value = "";
                return;
            }

            alert("PDF selected: " + file.name +
                  "\nReport analysis will be added later.");
        }
    });
}

const startButton = document.querySelector(".upload-btn");

if (startButton) {
    startButton.addEventListener("click", function () {
        document.querySelector(".upload-card")
            ?.scrollIntoView({ behavior: "smooth" });
    });
}
