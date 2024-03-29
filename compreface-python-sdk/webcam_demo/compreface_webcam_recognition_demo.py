"""
    Copyright(c) 2021 the original author or authors

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        https: // www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
    or implied. See the License for the specific language governing
    permissions and limitations under the License.
 """

import cv2
import argparse
import time
from SqlLog import cursor
from SqlLog import cnxn
import datetime
from threading import Thread

from compreface import CompreFace
from compreface.service import RecognitionService

def parseArguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("--api-key", help="CompreFace recognition service API key", type=str, default='e145d8e0-17be-474e-b507-49aba4866e38')
    parser.add_argument("--host", help="CompreFace host", type=str, default='http://localhost')
    parser.add_argument("--port", help="CompreFace port", type=str, default='8000')

    args = parser.parse_args()

    return args

class ThreadedCamera:
    def __init__(self, api_key, host, port):
        self.active = True
        self.results = []
        self.capture = cv2.VideoCapture("rtsp://admin:dev@2022@192.168.1.19/cam/realmonitor?channel=1subtype=1")
        # self.capture = cv2.VideoCapture("rtsp://ali:Ali@12345@192.168.1.110/cam/realmonitor?channel=1subtype=1")

        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 2)

        compre_face: CompreFace = CompreFace(host, port, {
            "limit": 0,
            "det_prob_threshold": 0.8,
            "prediction_count": 1,
            "face_plugins": "age,gender",
            "status": False
        })

        self.recognition: RecognitionService = compre_face.init_face_recognition(api_key)

        self.FPS = 1/30

        # Start frame retrieval thread
        self.thread = Thread(target=self.show_frame, args=())
        self.thread.daemon = True
        self.thread.start()

    def show_frame(self):
        count=0
        check=5
        print("Started")
        while self.capture.isOpened():
            (status, frame_raw) = self.capture.read()
            self.frame = cv2.flip(frame_raw, 1)

            if self.results:
                results = self.results
                for result in results:
                    box = result.get('box')
                    age = result.get('age')
                    gender = result.get('gender')
                    mask = result.get('mask')
                    subjects = result.get('subjects')
                    if box:
                        cv2.rectangle(img=self.frame, pt1=(box['x_min'], box['y_min']),
                                      pt2=(box['x_max'], box['y_max']), color=(0, 255, 0), thickness=2)
                        # if age:
                        #     age = f"Age: {age['low']} - {age['high']}"
                        #     cv2.putText(self.frame, age, (box['x_max'], box['y_min'] + 15),
                        #                 cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        # if gender:
                        #     gender = f"Gender: {gender['value']}"
                        #     cv2.putText(self.frame, gender, (box['x_max'], box['y_min'] + 35),
                        #                 cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        # if mask:
                        #     mask = f"Mask: {mask['value']}"
                        #     cv2.putText(self.frame, mask, (box['x_max'], box['y_min'] + 55),
                        #                 cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                        if subjects:
                            subjects = sorted(subjects, key=lambda k: k['similarity'], reverse=True)
                            subject = f"Subject: {subjects[0]['subject']}"
                            similarity = f"Similarity: {subjects[0]['similarity']}"
                            similarity=float(similarity.split(":")[1])
                            if similarity*100 > 95:
                                probability=str(round(similarity*100,2))+'%'
                                if count==check:
                                    cursor.execute("""
        		                    INSERT INTO FR_Logs5(DeviceId,Person_Name,Probability,Detected_At)
        		                    VALUES (?, ?, ?, ?)""", (0,subject,probability,datetime.datetime.now()))
                                    cnxn.commit()
                                    check=check+5
                                count=count+1
                                cv2.putText(self.frame, subject, (box['x_max'], box['y_min'] + 75),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                                cv2.putText(self.frame, probability, (box['x_max'], box['y_min'] + 95),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                            else:
                                subject = f"No known faces"
                                cv2.putText(self.frame, subject, (box['x_max'], box['y_min'] + 75),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2) 
                        else:
                            subject = f"No known faces"
                            cv2.putText(self.frame, subject, (box['x_max'], box['y_min'] + 75),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            cv2.imshow('CompreFace demo', self.frame)
            time.sleep(self.FPS)

            if cv2.waitKey(1) & 0xFF == 27:
                self.capture.release()
                cv2.destroyAllWindows()
                self.active=False

    def is_active(self):
        return self.active

    def update(self):
        if not hasattr(self, 'frame'):
            return

        _, im_buf_arr = cv2.imencode(".jpg", self.frame)
        byte_im = im_buf_arr.tobytes()
        data = self.recognition.recognize(byte_im)
        self.results = data.get('result')


if __name__ == '__main__':
    args = parseArguments()
    threaded_camera = ThreadedCamera(args.api_key, args.host, args.port)
    while threaded_camera.is_active():
        threaded_camera.update()