// Çizgi İzleyen Robot Araba - Atölye Elektronik
// 4 kanal çizgi sensörü (S1 en sol ... S4 en sağ) + L298N + 2 DC motor
// Ek kütüphane gerekmez.

#define IN1 5    // Sol motor (Motor A)
#define IN2 6
#define IN3 9    // Sağ motor (Motor B)
#define IN4 10

#define S1 A0    // en sol prob
#define S2 A1    // orta sol
#define S3 A2    // orta sağ
#define S4 A3    // en sağ prob

// Sensör siyah çizginin üstündeyken HIGH veriyorsa HIGH bırakın.
// Robot çizgiden kaçıyorsa (ters davranıyorsa) LOW yapın.
#define SIYAH HIGH

int HIZ   = 150;   // düz giderken motor hızı (0-255)
int DONUS = 130;   // dönüşte dıştaki tekerleğin hızı
int SERT  = 110;   // keskin dönüşte tekerleklerin hızı

int sonYon = 0;    // çizgi kaybolursa: -1 sola, 1 sağa ara

// sol / sag: -255 ... 255 (eksi = geri)
void motor(int sol, int sag) {
  if (sol >= 0) { analogWrite(IN1, sol);  digitalWrite(IN2, LOW); }
  else          { digitalWrite(IN1, LOW); analogWrite(IN2, -sol); }
  if (sag >= 0) { analogWrite(IN3, sag);  digitalWrite(IN4, LOW); }
  else          { digitalWrite(IN3, LOW); analogWrite(IN4, -sag); }
}

bool siyahMi(int pin) { return digitalRead(pin) == SIYAH; }

void setup() {
  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pinMode(S1, INPUT); pinMode(S2, INPUT);
  pinMode(S3, INPUT); pinMode(S4, INPUT);
  Serial.begin(9600);
  motor(0, 0);
  delay(1000);     // robotu çizgiye koymak için 1 sn
}

void loop() {
  bool a = siyahMi(S1), b = siyahMi(S2), c = siyahMi(S3), d = siyahMi(S4);

  // Seri Monitör'de sensörleri görmek için (9600 baud): 1 = siyah
  Serial.print(a); Serial.print(b); Serial.print(c); Serial.println(d);

  if (b && c)            { motor(HIZ, HIZ);       }  // tam ortada: düz
  else if (b && !c)      { motor(0, DONUS);        sonYon = -1; }  // hafif sola
  else if (c && !b)      { motor(DONUS, 0);        sonYon = 1;  }  // hafif sağa
  else if (a)            { motor(-SERT, SERT);     sonYon = -1; }  // keskin sola
  else if (d)            { motor(SERT, -SERT);     sonYon = 1;  }  // keskin sağa
  else {                                           // çizgi yok: son yöne ara
    if (sonYon < 0)      motor(-SERT, SERT);
    else if (sonYon > 0) motor(SERT, -SERT);
    else                 motor(0, 0);
  }
}
