# AutoYouTube — Android

## Как получить APK (бесплатно, без установки программ)

1. github.com → «+» → New repository → имя AutoYouTube → Public → Create.
2. На странице репозитория: uploading an existing file.
3. Распакуйте архив и перетащите ВСЁ содержимое папки autoyoutube (папки .github, assets, lib и файл pubspec.yaml) → Commit changes.
4. Вкладка Actions → Build AutoYouTube APK. Ждём зелёную галочку (5–10 мин).
5. Откройте сборку → внизу Artifacts → AutoYouTube-apk → скачается zip, внутри app-release.apk.
6. Перекиньте APK на телефон → откройте → разрешите «Установку из неизвестных источников» → Установить.

Если папка .github не загрузилась: Add file → Create new file → имя .github/workflows/build.yml → вставьте текст из файла build.yml → Commit.

## Обновление
Замените assets/AutoYouTube.html на новый → Commit → сборка запустится сама. Данные в приложении сохранятся при установке поверх.

## Подключение YouTube (один раз, бесплатно)

1. Откройте https://console.cloud.google.com и войдите аккаунтом вашего канала.
2. Сверху «Выбрать проект» → «Новый проект» → имя AutoYouTube → «Создать».
3. Меню → «APIs & Services» → «Library». Найдите и включите (Enable): **YouTube Data API v3** и **YouTube Analytics API**.
4. «OAuth consent screen» (Экран согласия) → тип **External** → заполните имя приложения и свою почту → сохраните.
   Затем нажмите **Publish app / In production** (иначе вход слетает каждые 7 дней). Предупреждение «приложение не проверено» — это нормально, это ваше личное приложение.
5. «Credentials» → «Create credentials» → «OAuth client ID» → тип **TVs and Limited Input devices** → «Создать».
6. Скопируйте **Client ID** и **Client secret** → в приложении: Ещё → Настройки → YouTube → вставьте → «Войти через Google».
7. Приложение покажет код. Нажмите «Открыть Google», введите код, выберите аккаунт канала. Если Google пишет «не проверено» → «Дополнительно» → «Перейти в AutoYouTube».

### Важно про загрузку видео
- Видео, загруженные через новый API-проект, YouTube держит **приватными**, пока проект не пройдёт бесплатную проверку: https://support.google.com/youtube/contact/yt_api_form
- До проверки: используйте кнопку «Сохранить / поделиться» → приложение YouTube, или после загрузки поменяйте доступ в YouTube Studio.
- Свою обложку YouTube разрешает только после подтверждения телефона на youtube.com/verify.
- Лимит API: ~6 загрузок видео в день (бесплатно).
