// Executed only inside the pinned network-none image; getArgs never invokes fetch.
import * as transform from '/opt/phase3a-opencode/packages/opencode/src/provider/transform.ts';
import { convertToModelMessages } from '/opt/phase3a-opencode/packages/opencode/node_modules/ai/dist/index.mjs';
import { createAnthropic } from '/opt/phase3a-opencode/packages/opencode/node_modules/@ai-sdk/anthropic/dist/index.mjs';
const modelInfo = {id:'claude-opus-5',providerID:'anthropic',api:{id:'claude-opus-5',npm:'@ai-sdk/anthropic'},capabilities:{input:{text:true},interleaved:false}};
let fetches = 0;
const model = createAnthropic({apiKey:'fixture-not-a-secret',fetch:()=>{fetches++;throw Error('HTTP forbidden')}})('claude-opus-5');
const cases = [
  {name:'signed-empty',part:{type:'reasoning',text:'',providerMetadata:{anthropic:{signature:'SYNTHETIC-SIGNATURE'}}}},
  {name:'signed-visible',part:{type:'reasoning',text:'SYNTHETIC ONLY',providerMetadata:{anthropic:{signature:'SYNTHETIC-SIGNATURE'}}}},
  {name:'redacted',part:{type:'reasoning',text:'',providerMetadata:{anthropic:{redactedData:'SYNTHETIC-OPAQUE-DATA'}}}},
  {name:'absent',part:null},
];
const rows=[];
for(const item of cases){
  const parts=[...(item.part?[item.part]:[]),{type:'text',text:'SYNTHETIC ANSWER'}];
  const converted=await convertToModelMessages([{id:'fixture',role:'assistant',parts}]);
  converted[0].content.push({type:'tool-call',toolCallId:'fixture-read',toolName:'read',input:{filePath:'/tmp/synthetic'}});
  converted.push({role:'tool',content:[{type:'tool-result',toolCallId:'fixture-read',toolName:'read',output:{type:'text',value:'SYNTHETIC RESULT'}}]});
  const counts=[];
  for(const prompt of [structuredClone(converted),transform.message(structuredClone(converted),modelInfo,{})]){
    const built=await model.getArgs({userSuppliedBetas:[],prompt,maxOutputTokens:16000,providerOptions:{anthropic:{thinking:{type:'adaptive'},effort:'high'}}});
    const content=built.args.messages[0].content;
    counts.push({opaque_blocks:content.filter(p=>['thinking','redacted_thinking'].includes(p.type)).length,
      empty_exact:content.some(p=>p.type==='thinking'&&p.thinking===''&&p.signature==='SYNTHETIC-SIGNATURE'),
      visible_exact:content.some(p=>p.type==='thinking'&&p.thinking==='SYNTHETIC ONLY'&&p.signature==='SYNTHETIC-SIGNATURE'),
      redacted_exact:content.some(p=>p.type==='redacted_thinking'&&p.data==='SYNTHETIC-OPAQUE-DATA'),
      tool_preserved:content.at(-1)?.id==='fixture-read'&&built.args.messages[1].content[0].tool_use_id==='fixture-read'});
  }
  rows.push({case:item.name,before_OpenCode:counts[0],after_OpenCode:counts[1]});
}
const interleaved=[{role:'assistant',content:[{type:'reasoning',text:'',providerOptions:{anthropic:{signature:'SYNTHETIC-1'}}},{type:'tool-call',toolCallId:'tool1',toolName:'read',input:{filePath:'/tmp/one'}},{type:'reasoning',text:'SYNTHETIC',providerOptions:{anthropic:{signature:'SYNTHETIC-2'}}},{type:'tool-call',toolCallId:'tool2',toolName:'read',input:{filePath:'/tmp/two'}}]},{role:'tool',content:['tool1','tool2'].map(id=>({type:'tool-result',toolCallId:id,toolName:'read',output:{type:'text',value:'SYNTHETIC'}}))}];
const normalized=transform.message(structuredClone(interleaved),modelInfo,{});
const ordered=await model.getArgs({userSuppliedBetas:[],prompt:normalized,maxOutputTokens:16000,providerOptions:{anthropic:{thinking:{type:'adaptive'},effort:'high'}}});
const order={valid_ends_in_tool:true,expected:['thinking','tool1','thinking','tool2'],actual:ordered.args.messages[0].content.map(p=>p.type==='tool_use'?p.id:p.type)};
const event=(type,data)=>`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`;
const truncated=event('message_start',{type:'message_start',message:{id:'fixture',type:'message',role:'assistant',model:'claude-opus-5',content:[],stop_reason:null,stop_sequence:null,usage:{input_tokens:1,output_tokens:0}}})+event('content_block_start',{type:'content_block_start',index:0,content_block:{type:'thinking',thinking:'',signature:''}})+event('content_block_delta',{type:'content_block_delta',index:0,delta:{type:'thinking_delta',thinking:''}});
let streamMocks=0;
const partialModel=createAnthropic({apiKey:'fixture-not-a-secret',fetch:async()=>{streamMocks++;return new Response(truncated,{headers:{'content-type':'text/event-stream'}})}})('claude-opus-5');
const partial=await partialModel.doStream({prompt:[{role:'user',content:[{type:'text',text:'SYNTHETIC'}]}],maxOutputTokens:16000,providerOptions:{anthropic:{thinking:{type:'adaptive'},effort:'high'}}});
const events=[];const reader=partial.stream.getReader();let terminal=false;
while(true){const item=await reader.read();if(item.done)break;events.push(item.value.type);if(item.value.type==='finish')terminal=true;}
if(terminal)throw Error('Truncated SDK stream unexpectedly completed');
console.log(JSON.stringify({fixture:true,fetch_invocations:fetches,rows,order,incomplete_stream:{mock_fetches:streamMocks,event_types:events,complete_terminal:false,eligible_for_next_admission:false}}));
