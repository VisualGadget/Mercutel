# Mercutel
Телеметрия для счётчика электроэнергии Меркурий 200.

Проект реализован на ESP8266 и MicroPython.
Возможности:
1. Подключение к CAN линии Меркурий 200 для снятия показаний счётчика;
2. Отправка показаний в систему "умного дома" Home Assistant по протоколу MQTT через WiFi;
3. Отправка показаний в Тюменский Расчётно-Информационный Центр (ТРИЦ).

# Текущее состояние
Устройство успешно работает со счётчиком Меркурий 200.02 в связке с Home Assistant. Отправка показаний в расчётный центр напрямую из ESP8266 на MicroPython сейчас невозможна по причине сломанной поддержки SSL, поэтому скрипт для передачи запускается средствами Home Assistant:

[Меркурий 200] --(CAN)--> [Mercutel] --(WiFi MQTT)--> [Home Assistant] --(интернет)--> [ТРИЦ]

## Отображение показаний в Home Assistant
![HA Widget](https://github.com/VisualGadget/Mercutel/raw/main/doc/Home%20Assistant/HA%20widget.png) ![HA Sensors](https://github.com/VisualGadget/Mercutel/raw/main/doc/Home%20Assistant/HA%20sensors.png)
