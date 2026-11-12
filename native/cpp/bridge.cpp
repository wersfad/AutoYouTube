#include <jni.h>
#include <whisper.h>
#include <atomic>
#include <fstream>
#include <sstream>
#include <vector>
#include <stdexcept>
#include <algorithm>
static std::atomic<bool> cancelled{false};
static std::string str(JNIEnv* e,jstring v){const char* p=e->GetStringUTFChars(v,nullptr);std::string s=p?p:"";if(p)e->ReleaseStringUTFChars(v,p);return s;}
static std::string json(const char* v){std::string s="\"";for(const unsigned char* p=(const unsigned char*)v;*p;p++){switch(*p){case '"':s+="\\\"";break;case '\\':s+="\\\\";break;case '\n':s+="\\n";break;case '\r':s+="\\r";break;case '\t':s+="\\t";break;default:if(*p>=32)s+=char(*p);}}return s+"\"";}
extern "C" JNIEXPORT void JNICALL Java_com_wersfad_autoyoutube_WhisperEngine_cancel(JNIEnv*,jclass){cancelled=true;}
extern "C" JNIEXPORT jstring JNICALL Java_com_wersfad_autoyoutube_WhisperEngine_decode(JNIEnv* e,jclass,jstring model,jstring pcm,jint threads,jstring language){
 whisper_context* ctx=nullptr;
 try{
  cancelled=false;std::string mp=str(e,model),pp=str(e,pcm),lang=str(e,language);
  std::ifstream f(pp,std::ios::binary|std::ios::ate);if(!f)throw std::runtime_error("Cannot open PCM");const std::streamoff bytes=f.tellg();if(bytes<=0||bytes>16000*4*240||bytes%4!=0)throw std::runtime_error("Invalid PCM length");f.seekg(0);std::vector<float> samples(size_t(bytes)/4);f.read(reinterpret_cast<char*>(samples.data()),bytes);if(!f)throw std::runtime_error("Incomplete PCM");
  auto cp=whisper_context_default_params();cp.use_gpu=false;ctx=whisper_init_from_file_with_params(mp.c_str(),cp);if(!ctx)throw std::runtime_error("Whisper model could not be loaded");
  auto p=whisper_full_default_params(WHISPER_SAMPLING_GREEDY);p.n_threads=std::max(1,std::min(4,int(threads)));p.language=lang.c_str();p.translate=false;p.print_progress=false;p.print_realtime=false;p.print_timestamps=false;p.no_context=true;p.abort_callback=[](void*){return cancelled.load();};p.abort_callback_user_data=nullptr;
  if(whisper_full(ctx,p,samples.data(),int(samples.size()))!=0)throw std::runtime_error(cancelled?"Stopped":"Speech recognition failed");
  std::ostringstream out;out<<"[";int n=whisper_full_n_segments(ctx);for(int i=0;i<n;i++){if(i)out<<",";out<<"{\"start\":"<<whisper_full_get_segment_t0(ctx,i)/100.0<<",\"end\":"<<whisper_full_get_segment_t1(ctx,i)/100.0<<",\"text\":"<<json(whisper_full_get_segment_text(ctx,i))<<"}";}out<<"]";whisper_free(ctx);ctx=nullptr;return e->NewStringUTF(out.str().c_str());
 }catch(const std::exception& ex){if(ctx)whisper_free(ctx);e->ThrowNew(e->FindClass("java/lang/RuntimeException"),ex.what());return nullptr;}
}
