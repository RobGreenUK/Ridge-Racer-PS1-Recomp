#pragma once
// Only car/shadow contact uses this shader. XY and texture projection are
// unchanged; a monotonic depth compression keeps overlapping car parts ordered
// immediately in front of their nearby road plane. Nearer walls still occlude.
struct ContactDepthShader {
    GLuint program=0;GLint roadLocation=-1,textureLocation=-1;
    void close(){if(program)glDeleteProgram(program);program=0;}
    void prepare(){
        if(program)return;
        const char*vertex=R"GLSL(#version 120
void main(){
    gl_Position=ftransform();
    gl_TexCoord[0]=gl_MultiTexCoord0;
    gl_FrontColor=gl_Color;
}
)GLSL";
        const char*fragment=R"GLSL(#version 120
uniform sampler2D tex;
uniform vec3 road;
void main(){
    gl_FragColor=texture2DProj(tex,gl_TexCoord[0])*gl_Color;
    float r=dot(road,vec3(gl_FragCoord.xy,1.0));
    float z=gl_FragCoord.z;
    // Reserve a small perspective-relative band for the road overlap.
    // Unlike a hard clamp, this preserves ordering among body, tyres and shadow.
    float e=max(0.000002,(1.0-r)/256.0);
    if(r>0.0&&r<1.0&&z>r-e)z=r-e/(1.0+(z-(r-e))/e);
    gl_FragDepth=z;
}
)GLSL";
        auto compile=[](GLenum kind,const char*source){
            GLuint shader=glCreateShader(kind);glShaderSource(shader,1,&source,nullptr);glCompileShader(shader);
            GLint ok;glGetShaderiv(shader,GL_COMPILE_STATUS,&ok);
            if(!ok){char msg[2048];glGetShaderInfoLog(shader,sizeof msg,nullptr,msg);glDeleteShader(shader);throw std::runtime_error(std::string("car contact shader: ")+msg);}
            return shader;
        };
        GLuint v=0,f=0;
        try{
            v=compile(GL_VERTEX_SHADER,vertex);f=compile(GL_FRAGMENT_SHADER,fragment);
            program=glCreateProgram();glAttachShader(program,v);glAttachShader(program,f);glLinkProgram(program);
            GLint ok;glGetProgramiv(program,GL_LINK_STATUS,&ok);
            if(!ok){char msg[2048];glGetProgramInfoLog(program,sizeof msg,nullptr,msg);throw std::runtime_error(std::string("car contact shader link: ")+msg);}
            roadLocation=glGetUniformLocation(program,"road");textureLocation=glGetUniformLocation(program,"tex");
        }catch(...){if(v)glDeleteShader(v);if(f)glDeleteShader(f);close();throw;}
        glDeleteShader(v);glDeleteShader(f);
    }
    void use(Vec plane){
        glUseProgram(plane.z?program:0);
        if(plane.z){glUniform1i(textureLocation,0);glUniform3f(roadLocation,plane.x,plane.y,plane.z);}
    }
};
