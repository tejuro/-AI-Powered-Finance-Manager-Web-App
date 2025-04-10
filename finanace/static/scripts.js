function handleFormSubmit(event, formId, resultId) {
    event.preventDefault();
    const form = document.getElementById(formId);
    const formData = new FormData(form);
    fetch(form.action, {
        method: form.method,
        body: formData
    })
    .then(res => res.text())
    .then(data => {
        const resultBox = document.getElementById(resultId);
        resultBox.innerText = data;
        resultBox.classList.add("popup");
        setTimeout(() => {
            resultBox.classList.remove("popup");
            resultBox.innerText = "";
        }, 3000);
    })
    .catch(err => {
        document.getElementById(resultId).innerText = "Something went wrong.";
    });
}
