/* vendored from three@0.180.0 · 裸模块名已改为相对路径（壳的 CSP 不许 importmap）
   来源：vendor/node_modules/three/examples/jsm/shaders/LuminosityHighPassShader.js
   重建：py -3.14 tools/codex-scripts/vendor_three.py --write
   本文件是**第三方代码的原样拷贝 + 一处 import 改写**，不要在这里加业务逻辑。 */
import {
	Color
} from './three.module.min.js';

/**
 * @module LuminosityHighPassShader
 * @three_import import { LuminosityHighPassShader } from 'three/addons/shaders/LuminosityHighPassShader.js';
 */

/**
 * Luminosity high pass shader.
 *
 * @constant
 * @type {ShaderMaterial~Shader}
 */
const LuminosityHighPassShader = {

	name: 'LuminosityHighPassShader',

	uniforms: {

		'tDiffuse': { value: null },
		'luminosityThreshold': { value: 1.0 },
		'smoothWidth': { value: 1.0 },
		'defaultColor': { value: new Color( 0x000000 ) },
		'defaultOpacity': { value: 0.0 }

	},

	vertexShader: /* glsl */`

		varying vec2 vUv;

		void main() {

			vUv = uv;

			gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

		}`,

	fragmentShader: /* glsl */`

		uniform sampler2D tDiffuse;
		uniform vec3 defaultColor;
		uniform float defaultOpacity;
		uniform float luminosityThreshold;
		uniform float smoothWidth;

		varying vec2 vUv;

		void main() {

			vec4 texel = texture2D( tDiffuse, vUv );

			float v = luminance( texel.xyz );

			vec4 outputColor = vec4( defaultColor.rgb, defaultOpacity );

			float alpha = smoothstep( luminosityThreshold, luminosityThreshold + smoothWidth, v );

			gl_FragColor = mix( outputColor, texel, alpha );

		}`

};

export { LuminosityHighPassShader };
