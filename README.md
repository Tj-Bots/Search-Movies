# ***חיפוש סרטים***

בוט טלגרם לחיפוש סרטים במהירות ובנוחות.

#
# פקודות הבוט ⚙️
<details>
<summary><b>⌨️ פקודות למשתמשים:</b></summary>

<br>

- `/start` - התחל בוט.
- `/stats` - סטטיסטיקות הבוט.
- `/id` - קבלת מזהה משתמש/צ'אט.
- `/info` - קבלת מידע על משתמש כמו: פרופיל, שם, יוזר, איידי וכו'...
- `/tts` - תמלל הודעת טקסט לשמע.
- `/font` - משנה טקסט באנגלית לטקסט יפה.
- `/share` - שיתוף טקסט.
- `/paste` - העלאת קובץ טקסט/הודעת טקסט לאתר Pastebin.
- `/stickerid` - מביא את הid של הסטיקר שהגיבו עליו.
- `/json` - קבלת המידע הטכני (JSON) של ההודעה.
- `/written` - מביא את הid של הסטיקר שהגיבו עליו

</details>


<details>
<summary><b>⌨️ פקודות למנהלים:</b></summary>
  
<br>

<b>---- ניהול תוכן ----</b>

- `/index` [link] - [start] -  אינדקס לערוץ. מוסיף את כל הקבצים שיש בערוץ למסד נתונים.
- `/newindex` [id] - מוסיף כל קובץ חדש שנשלח בערוץ. (מוסיף רק הודעות חדשות)
- `/channels` - ניהול ערוצים במעקב.

<b>---- מערכת ----</b>

- `/clean` - מחיקת כל הקבצים מהאינדקס. או כל המשתמשים שנשמרו.
- `/broadcast` - שידור הודעה לכל המשתמשים.
- `/broadcast_groups` - שידור הודעה לכל הקבוצות.
- `/restart` - הפעלה מחדש לבוט.


  <b>---- חסימת משתמשים ----</b>
  
- `/ban` [id] - חסימת משתמש.
- `/unban` [ID] - שחרור משתמש.
- `/ban_chat` [ID] - חסימת קבוצה.
- `/unban_chat` [ID] - שחרור קבוצה.
-  `/leave` [ID] - יציאה מקבוצה (ללא חסימה).
</details>

#
# 🛠 משתנים (Variables)
<details>
<summary><b>משתנים </></b></summary>
כדי שהבוט יעבוד, חובה להגדיר את המשתנים הבאים בקובץ `.env` או בשרת:

| משתנה | חובה? | מאיפה להשיג? |
| :--- | :---: | :--- |
| `API_ID` | ✅ | [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | ✅ | [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | ✅ | מבוט האב: [@BotFather](https://t.me/BotFather) |
| `MONGO_URI` | ✅ | מהאתר של [MongoDB](https://www.mongodb.com) |
| `DB_NAME` | ✅ | בחרו שם רנדומלי באנגלית (למשל: `MovieBot`) |
| `ADMINS` | ✅ | שלחו `/me` לבוט [@GetChatID_IL_BOT](https://t.me/GetChatID_IL_BOT) |
| `LOG_CHANNEL` | ✅ | הוסיפו את הבוט לערוץ ושלחו שם הודעה, העבירו אותה ל- [@GetChatID_IL_BOT](https://t.me/GetChatID_IL_BOT) |
| `UPDATE_CHANNEL` | ❌ | שם המשתמש של הערוץ (בלי @) |
| `REQUEST_GROUP` | ❌ | קישור לקבוצת הבקשות/תמיכה |
| `PHOTO_URL` | ❌ | קישור ישיר לתמונה (שישמש כקאבר לבוט) |

</details>

#
# 🚀 הרצת הבוט

<details>
<summary><b>🐧 הרצה בשרת לינוקס (VPS / Terminal)</b></summary>

<br>

# עדכון והתקנת גיט ופייתון:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install git python3-pip -y
   ```

**שכפול התיקייה (Clone):**
   ```bash
   git clone https://github.com/Tj-Bots/Search-Movies
   cd Search-Movies
   ```

**התקנת הספריות הדרושות:**

```
pip3 install -r requirements.txt
```

**יצירת קובץ משתנים:**
שנו את השם של sample_env ל-.env ועכרו אותו עם הפרטים שלכם:
```
cp sample.env .env
nano .env
```

**הפעלת הבוט:**
```
python3 bot.py
```
</details>

<details>
<summary><b>🐳 הרצה באמצעות Docker</b></summary>
  
1. **בניית האימג' (Build):**

```
docker build . -t movie-bot
```

2. ה**רצת הקונטיינר (Run):**
ודא שקובץ ה-.env שלך מעודכן ומלא בפרטים לפני ההרצה.
```
docker run --env-file .env movie-bot
```
</details>

#
**בוט ניסיון: [@SearchGram_RoBot](https://t.me/searchgram_robot)** <br>
**ערוץ עדכונים: [@SearchGram_Bots](https://t.me/searchgram_bots)**
#
©️ הבוט נוצר על ידי [@BOSS1480](https://t.me/BOSS1480)
