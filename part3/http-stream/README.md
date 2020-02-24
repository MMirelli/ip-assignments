## Cases:

1) 720p stream from Many Vehicles to One Vehicle or Edge -> WebRTC (or DASH/HLS)
    - HTTP Streaming from MULTIPLE apache docker containers to one client (web browser viewing multiple html+js clients).
    - WebRTC (to be implemented...)  

2) 720p stream from One Vehicle to Many -> DASH/HLS or WebRTC
    - HTTP Streaming from VM apache server to many clients.
    - WebRTC (under consideration...)

# Setting up HTTP Streaming (DASH & HLS) with docker

1. Make sure docker and docker-compose are installed.

2. Download dash and hls video data from google drive and copy it into `dashvideo` and `hlsvideo` folders.  
https://drive.google.com/open?id=13Pek2o67vwZ3qokCvn6S0-MPw0B6j5jm

3. Run `docker-compose up` to start 3 apache2 docker containers. Docker-compose also adds the contents of `clients` folder to the server document root and the dash and hls video data to corresponding directories `dash` and `hls` on the server.

4.  The containers should be available at:  
http://localhost:8091/  
http://localhost:8092/  
http://localhost:8093/  
The players are located at the server document root folder  
http://localhost:8091/playerdash.html  
http://localhost:8091/playerhls.html  

5. Enter the corresponding link to the video manifest file to the url field on the player.  
e.g. http://localhost:8091/dash/video.mpd  
or http://localhost:8091/hls/manifest.m3u8  
Remember to match the port number for the player and video manifest urls


# HTTPS Streaming with a VM

- Install virtualbox and vagrant
- `cd` to the directory with vagrantfile (should be in `http-stream`)
- Run  
```
vagrant up
```
- Note: Copying the videofiles to the VM will take some time
- Then `ssh` into the VM  
```
ssh vagrant@localhost -p 20004
```
- Default password of user vagrant is: vagrant

- Edit document-root-location at:

```
vagrant@ia:~$ sudo nano /etc/apache2/apache2.conf
```
- Edit directory location from `/var/www` to `/home/vagrant/var/www/`

```
vagrant@ia:~$ sudo nano /etc/apache2/sites-enabled/000-default.conf
```

- Edit DocumentRoot to match `/home/vagrant/var/www/`
- Restart apache to enable the changes.

```
vagrant@ia:~$ sudo systemctl restart apache
```

After this you should be able to access the server at  
http://localhost:8094/  




# Preprocessing video data for HTTP Streaming (no need to do this with the video data from google drive)

## DASH

#### Audio  
```
ffmpeg -i video.mp4 -c:a copy -vn video-audio.mp4
```

#### Video  

```
ffmpeg -i video.mp4 -an -c:v libx264 -x264opts 'keyint=60:min-keyint=60' -b:v 5300k -maxrate 5300k -bufsize 2650k -vf 'scale=-1:1080' video-1080.mp4

ffmpeg -i video.mp4 -an -c:v libx264 -x264opts 'keyint=60:min-keyint=60' -b:v 2400k -maxrate 2400k -bufsize 1200k -vf 'scale=-1:720' video-720.mp4

ffmpeg -i video.mp4 -an -c:v libx264 -x264opts 'keyint=60:min-keyint=60' -b:v 1060k -maxrate 1060k -bufsize 530k -vf 'scale=-1:478' video-480.mp4

ffmpeg -i video.mp4 -an -c:v libx264 -x264opts 'keyint=60:min-keyint=60' -b:v 600k -maxrate 600k -bufsize 300k -vf 'scale=-1:360' video-360.mp4

ffmpeg -i video.mp4 -an -c:v libx264 -x264opts 'keyint=60:min-keyint=60' -b:v 260k -maxrate 260k -bufsize 130k -vf 'scale=-1:242' video-240.mp4
```

#### Manifest
```
MP4Box -dash 1000 -rap -frag-rap -profile onDemand -out video.mpd video-1080.mp4 video-720.mp4 video-480.mp4 video-360.mp4 video-240.mp4 video-audio.mp4
```

------
## HLS

Run inside `http-stream` the following commands:

```
mkdir hlsvideo/1080p60
mkdir hlsvideo/720p60
mkdir hlsvideo/480p60
mkdir hlsvideo/360p60
mkdir hlsvideo/240p60
```

And then the following where `video.mp4` is the name of the video you wnat to preprocess.


```
ffmpeg -i hlsvideo/video.mp4 -c:a copy -c:v libx264 -flags +cgop -g 60 -b:v 5300k -maxrate 5300k -bufsize 2650k -vf 'scale=-1:1080' -hls_time 1 -hls_playlist_type vod -hls_segment_filename hlsvideo/1080p60/1080p_%03d.ts hlsvideo/1080p60/manifest.m3u8

ffmpeg -i hlsvideo/video.mp4 -c:a copy -c:v libx264 -flags +cgop -g 60 -b:v 2400k -maxrate 2400k -bufsize 1200k -vf 'scale=-1:720' -hls_time 1 -hls_playlist_type vod -hls_segment_filename hlsvideo/720p60/720p_%03d.ts hlsvideo/720p60/manifest.m3u8

ffmpeg -i hlsvideo/video.mp4 -c:a copy -c:v libx264 -flags +cgop -g 60 -b:v 1060k -maxrate 1060k -bufsize 530k -vf 'scale=-1:478' -hls_time 1 -hls_playlist_type vod -hls_segment_filename hlsvideo/480p60/480p_%03d.ts hlsvideo/480p60/manifest.m3u8

ffmpeg -i hlsvideo/video.mp4 -c:a copy -c:v libx264 -flags +cgop -g 60 -b:v 600k -maxrate 600k -bufsize 300k -vf 'scale=-1:360' -hls_time 1 -hls_playlist_type vod -hls_segment_filename hlsvideo/360p60/360p_%03d.ts hlsvideo/360p60/manifest.m3u8

ffmpeg -i hlsvideo/video.mp4 -c:a copy -c:v libx264 -flags +cgop -g 60 -b:v 260k -maxrate 260k -bufsize 130k -vf 'scale=-1:242' -hls_time 1 -hls_playlist_type vod -hls_segment_filename hlsvideo/240p60/240p_%03d.ts hlsvideo/240p60/manifest.m3u8
```

