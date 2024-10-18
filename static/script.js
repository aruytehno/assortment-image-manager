document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.images').forEach(function (sortableContainer) {
        new Sortable(sortableContainer, {
            animation: 150,
            onEnd: function (evt) {
                let rowId = sortableContainer.id.split('-')[1];  // Используем артикул
                let imgUrls = [];
                sortableContainer.querySelectorAll('.sortable-img').forEach(function (img) {
                    imgUrls.push(img.getAttribute('data-url'));
                });

                fetch(`/reorder_images/${rowId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ imgUrls: imgUrls })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        // alert('Порядок изображений сохранен');
                    } else {
                        alert('Ошибка сохранения порядка');
                    }
                })
                .catch(error => {
                    alert('Ошибка при отправке данных');
                });
            }
        });
    });
});


function deleteImage(artikul, imgUrl) {
    if (confirm("Вы уверены, что хотите удалить это изображение?")) {
        fetch(`/delete_image/${artikul}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ imgUrl: imgUrl })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Изображение успешно удалено');
                // Удаляем изображение из DOM, не перезагружая страницу
                document.querySelector(`img[data-url='${imgUrl}']`).parentElement.remove();
            } else {
                alert('Ошибка при удалении изображения: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Ошибка:', error);
        });
    }
}
